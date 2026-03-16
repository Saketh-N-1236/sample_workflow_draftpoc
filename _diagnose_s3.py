"""Diagnose Scenario 3 — trace exactly what the diff parser and DB produce."""
import sys; sys.path.insert(0, ".")
import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from git_diff_processor.utils.diff_parser import parse_git_diff, build_search_queries
from deterministic.db_connection import get_connection_with_schema

DIFF = """diff --git a/src/helpers/utilities.js b/src/helpers/utilities.js
--- a/src/helpers/utilities.js
+++ b/src/helpers/utilities.js
@@ -176,23 +176,17 @@ export function capitalizeFirstLetter(string) {
 }
 
 export function capitalizeFirstLetter(string) {
-  if (string && typeof string === 'string') {
+  if (string && typeof string === 'string' && string.trim().length > 0) {
     if (checkWhiteSpace(string)) {
-      let stringUppercase = string.split(' ');
-      let parseString = '';
-      for (let index = 0; index < stringUppercase.length; index++) {
-        let texts =
-          stringUppercase[index].length > 0
-            ? stringUppercase[index].charAt(0).toUpperCase() +
-              stringUppercase[index].slice(1)
-            : '';
-        parseString += index > 0 ? ' ' + texts : texts;
-      }
-      return parseString;
-    } else {
-      return string.charAt(0).toUpperCase() + string.slice(1);
+      return string
+        .split(' ')
+        .filter(w => w.length > 0)
+        .map(w => w.charAt(0).toUpperCase() + w.slice(1))
+        .join(' ');
     }
+    return string.charAt(0).toUpperCase() + string.slice(1);
   }
+  return '';
 }
 
diff --git a/src/reducer/toastReducer.js b/src/reducer/toastReducer.js
--- a/src/reducer/toastReducer.js
+++ b/src/reducer/toastReducer.js
@@ -1,13 +1,19 @@
 import {TOAST} from './actiotypes';
 
-const initialState = {showToast: null};
+const initialState = {
+  showToast:  null,
+  toastType:  'info',
+  toastQueue: [],
+};
 
 export const toastReducer = (state = initialState, action) => {
   switch (action.type) {
     case TOAST:
       return {
         ...state,
-        showToast: action.toast,
+        showToast:  action.toast,
+        toastType:  action.toastType ?? state.toastType,
+        toastQueue: action.queue    ?? state.toastQueue,
       };
     default:
       return state;
"""

schema = "test_repo_261b672a"

print("=" * 60)
print("STEP 1: What does parse_git_diff extract?")
print("=" * 60)
parsed = parse_git_diff(DIFF)
print(f"  changed_files  : {parsed['changed_files']}")
print(f"  changed_classes: {parsed['changed_classes']}")
print(f"  changed_methods: {parsed['changed_methods']}")
for fc in parsed['file_changes']:
    print(f"  file: {fc['file']}")
    print(f"    methods: {fc['changed_methods']}")
    print(f"    classes: {fc['changed_classes']}")

print()
print("=" * 60)
print("STEP 2: What does build_search_queries build?")
print("=" * 60)
sq = build_search_queries(parsed['file_changes'], diff_content=DIFF)
print(f"  exact_matches    : {sorted(sq['exact_matches'])}")
print(f"  module_matches   : {sorted(sq['module_matches'])}")
print(f"  changed_functions: {sq['changed_functions']}")
print(f"  test_file_cands  : {sq['test_file_candidates'][:5]}")

print()
print("=" * 60)
print("STEP 3: What does the DB have for capitalizeFirstLetter?")
print("=" * 60)
with get_connection_with_schema(schema) as conn:
    with conn.cursor() as cur:
        # reverse_index
        cur.execute(
            f"SELECT production_class, test_id FROM {schema}.reverse_index "
            f"WHERE production_class ILIKE %s ORDER BY test_id",
            ('%capitalizeFirstLetter%',)
        )
        rows = cur.fetchall()
        print(f"  reverse_index (capitalizeFirstLetter): {len(rows)} rows")
        for r in rows: print(f"    {r[0]} -> {r[1]}")

        # function_mapping
        cur.execute(
            f"SELECT test_id, function_name FROM {schema}.test_function_mapping "
            f"WHERE function_name ILIKE %s ORDER BY test_id",
            ('%capitalizeFirstLetter%',)
        )
        rows = cur.fetchall()
        print(f"  function_mapping (capitalizeFirstLetter): {len(rows)} rows")
        for r in rows: print(f"    {r[0]} -> {r[1]}")

        # toastReducer
        cur.execute(
            f"SELECT production_class, test_id FROM {schema}.reverse_index "
            f"WHERE production_class ILIKE %s ORDER BY test_id",
            ('%toast%',)
        )
        rows = cur.fetchall()
        print(f"  reverse_index (toastReducer): {len(rows)} rows")
        for r in rows: print(f"    {r[0]} -> {r[1]}")

        # utilities module
        cur.execute(
            f"SELECT production_class, test_id FROM {schema}.reverse_index "
            f"WHERE production_class ILIKE %s ORDER BY test_id",
            ('%utilities%',)
        )
        rows = cur.fetchall()
        print(f"  reverse_index (utilities): {len(rows)} rows")
        for r in rows[:20]: print(f"    {r[0]} -> {r[1]}")

        # What test_ids come back for test_0001 and test_0034?
        cur.execute(
            f"SELECT test_id, method_name, class_name FROM {schema}.test_registry "
            f"WHERE test_id IN ('test_0001', 'test_0034') ORDER BY test_id"
        )
        rows = cur.fetchall()
        print()
        print("  test_0001 and test_0034 details:")
        for r in rows: print(f"    {r[0]}: class={r[2]}, method={r[1]}")

        # function_mapping for test_0001 — why was it selected?
        cur.execute(
            f"SELECT function_name FROM {schema}.test_function_mapping "
            f"WHERE test_id = 'test_0001' ORDER BY function_name"
        )
        rows = cur.fetchall()
        print(f"  function_mapping for test_0001: {[r[0] for r in rows]}")

        cur.execute(
            f"SELECT function_name FROM {schema}.test_function_mapping "
            f"WHERE test_id = 'test_0034' ORDER BY function_name"
        )
        rows = cur.fetchall()
        print(f"  function_mapping for test_0034: {[r[0] for r in rows]}")
