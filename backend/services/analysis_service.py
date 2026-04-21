"""Service for running test analysis pipeline."""

import sys
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
import logging
import os

# Add backend/ to path so all sub-packages are importable
_backend_path = Path(__file__).parent.parent
if str(_backend_path) not in sys.path:
    sys.path.insert(0, str(_backend_path))

from test_analysis.engine.repo_analyzer import RepoAnalyzer
from deterministic.loader import load_to_db
from deterministic.db_connection import get_connection_with_schema

logger = logging.getLogger(__name__)


class AnalysisService:
    """
    Service for executing the test analysis pipeline.

    Pipeline (single RepoAnalyzer pass, no subprocesses):
        PHASE 1  RepoAnalyzer.analyze()  — detect languages → scan → extract (parallel)
        PHASE 2  load_to_db()            — write results to PostgreSQL
        PHASE 3  _embed_in_process()     — embed tests via OpenAI and store in Pinecone

    Previous design ran RepoAnalyzer THREE times (old PHASE 2 dispatch + PHASE 5 + embedding
    subprocess calling load_tests_from_analysis).  This version runs it exactly once.
    """

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        if str(self.project_root) not in sys.path:
            sys.path.insert(0, str(self.project_root))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_pipeline(
        self,
        repo_path: str,
        test_repo_id: str = None,
        schema_name: str = None,
        progress_callback=None,
    ) -> Dict:
        """
        Run the test analysis pipeline.

        Args:
            repo_path:         Path to the (extracted) test repository.
            test_repo_id:      Optional test_repo_id (stored in DB / Pinecone namespace).
            schema_name:       PostgreSQL schema name.  Falls back to TEST_REPO_SCHEMA env.
            progress_callback: Async callable(message: str) for streaming progress.

        Returns:
            Dictionary with analysis results (or {'success': False, 'error': ...}).
        """
        repo_path_obj = Path(repo_path).resolve()
        if not repo_path_obj.exists():
            raise FileNotFoundError(f"Repository path does not exist: {repo_path_obj}")

        # Resolve effective schema
        effective_schema = (
            schema_name
            or os.getenv("TEST_REPO_SCHEMA")
            or self._schema_from_db(test_repo_id)
            or "planon1"
        )

        # Keep env vars in sync for any legacy code that reads them
        os.environ["TEST_REPO_PATH"] = str(repo_path_obj)
        os.environ["TEST_REPO_SCHEMA"] = effective_schema
        if test_repo_id:
            os.environ["TEST_REPO_ID"] = test_repo_id

        logger.info(f"[ANALYSIS] Starting pipeline for {repo_path_obj} (schema={effective_schema})")

        async def _progress(msg: str) -> None:
            logger.info(f"[ANALYSIS] {msg}")
            if progress_callback:
                try:
                    await progress_callback(msg)
                except Exception:
                    pass

        try:
            # ── PHASE 1: Analyse (detect + scan + extract in parallel) ────────
            await _progress("PHASE 1 — Analysing test repository (parallel language dispatch)...")
            loop = asyncio.get_event_loop()
            analysis_result = await loop.run_in_executor(
                None,
                lambda: RepoAnalyzer().analyze(
                    repo_path_obj,
                    schema_name=effective_schema,
                    repo_id=test_repo_id or "",
                ),
            )

            if not analysis_result.all_tests:
                logger.warning("[ANALYSIS] No tests extracted from repository")
                return {"success": False, "error": "No tests found in repository"}

            await _progress(f"  [OK] {analysis_result.total_tests} test(s) extracted from {analysis_result.detected_languages}")

            # ── PHASE 2: Load to DB ───────────────────────────────────────────
            await _progress("PHASE 2 — Loading results to database...")
            try:
                with get_connection_with_schema(effective_schema) as conn:
                    load_stats = load_to_db(conn, analysis_result, effective_schema)
                await _progress(f"  [OK] Loaded {analysis_result.total_tests} tests into DB")
                logger.info(f"[ANALYSIS] Load stats: {load_stats}")
            except Exception as load_err:
                logger.error(f"[ANALYSIS] DB load failed: {load_err}", exc_info=True)
                await _progress(f"  [ERROR] DB load failed: {load_err}")

            # ── PHASE 3: Embed in-process (no subprocess) ─────────────────────
            await _progress("PHASE 3 — Generating embeddings (in-process, batched)...")
            await self._embed_in_process(
                analysis_result=analysis_result,
                test_repo_id=test_repo_id,
                progress_callback=progress_callback,
            )

            return {
                "success": True,
                "total_tests": analysis_result.total_tests,
                "total_test_classes": len({t.describe for t in analysis_result.all_tests if t.describe}),
                "total_test_methods": analysis_result.total_tests,
                "functions_extracted": len(analysis_result.function_mappings),
                "modules_identified": len(analysis_result.reverse_index),
                "total_dependencies": len(analysis_result.dependencies),
                "framework": analysis_result.framework,
                "files_analyzed": sum(
                    lr.files_analyzed for lr in analysis_result.languages.values()
                ),
                "test_files": sum(
                    lr.files_analyzed for lr in analysis_result.languages.values()
                ),
            }

        except Exception as exc:
            logger.error(f"[ANALYSIS] Pipeline failed: {exc}", exc_info=True)
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _schema_from_db(self, test_repo_id: Optional[str]) -> Optional[str]:
        """Look up schema_name from the test_repositories table."""
        if not test_repo_id:
            return None
        try:
            from services.test_repo_service import get_test_repository
            repo = get_test_repository(test_repo_id)
            return (repo or {}).get("schema_name")
        except Exception as exc:
            logger.warning(f"[ANALYSIS] Could not fetch schema for {test_repo_id}: {exc}")
            return None

    async def _embed_in_process(self, analysis_result, test_repo_id: Optional[str], progress_callback=None):
        """
        Generate and store embeddings for all tests — in the current process.

        Previously this was a subprocess call to embedding_generator.py which spawned a fresh
        Python interpreter, re-imported every module, and ran RepoAnalyzer a SECOND time via
        load_tests_from_analysis().  This method skips all that and feeds the already-available
        AnalysisResult directly into store_embeddings().
        """
        try:
            from semantic.embedding_generation.embedding_generator import store_embeddings

            # Build the list expected by store_embeddings (same shape as load_tests_from_analysis)
            tests: List[Dict] = []
            for t in analysis_result.all_tests:
                tests.append(
                    {
                        "test_id": t.id,
                        "method_name": t.full_name,
                        "class_name": t.describe or "",
                        "content": t.content or "",
                        "file_path": t.file,
                        "relative_path": Path(t.file).name if t.file else "",
                        "language": t.language,
                        "line_number": t.line_number,
                        "test_repo_id": test_repo_id or "",
                        "description": t.description or t.full_name,
                        "is_analysis_based": True,
                    }
                )

            if not tests:
                logger.warning("[EMBED] No tests to embed")
                return

            logger.info(f"[EMBED] Embedding {len(tests)} test(s) in-process (batched, no subprocess)")
            stored, failed, chunks = await store_embeddings(tests, conn=None)

            if stored == 0 and len(tests) > 0:
                logger.warning("[EMBED] No embeddings stored — possible dimension mismatch or API error")
            else:
                logger.info(f"[EMBED] Done — stored={stored}, failed={failed}, chunks={chunks}")

            if progress_callback:
                try:
                    await progress_callback(f"  [OK] {stored} embeddings stored to Pinecone")
                except Exception:
                    pass

        except Exception as exc:
            logger.error(f"[EMBED] In-process embedding failed: {exc}", exc_info=True)
            if progress_callback:
                try:
                    await progress_callback(f"  [ERROR] Embedding failed: {exc}")
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Deprecated stubs (kept to avoid AttributeError if called externally)
    # ------------------------------------------------------------------

    async def _load_to_database(self, *args, **kwargs):
        logger.warning("[DEPRECATED] _load_to_database() is no longer used.")

    async def _generate_embeddings(self, *args, **kwargs):
        logger.warning("[DEPRECATED] _generate_embeddings() is no longer used. Embeddings are now generated in-process by _embed_in_process().")
