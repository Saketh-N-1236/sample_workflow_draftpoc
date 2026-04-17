# Smart Test Selector — Beginner's Guide

> **Who is this for?** Anyone who is new to this project and wants to understand what it does, why it exists, and how it works — no coding experience needed.

---

## The Problem It Solves

Imagine you are working on a large software project that has **500 automated tests**.

Every time a developer changes even one line of code, the team runs all 500 tests to make sure nothing broke. This takes a long time — sometimes **30 to 60 minutes**.

But here is the thing: if a developer only changed a button color, do you really need to run all 500 tests? Of course not. Maybe only **5 or 10 tests** are actually related to that change.

**This system solves that problem.** It automatically figures out *which tests are relevant* to a code change, so the team only runs those — saving time and money.

---

## What the System Does (in Simple Terms)

1. A developer **makes a code change** and wants to merge it into the main codebase.
2. The system **reads the code change** (called a "diff" — the before and after of what changed).
3. It **figures out which tests** are related to that change.
4. It shows the developer a list: *"Out of 500 tests, only these 12 need to run."*

That's it. The whole system is a smart shortcut that says: **"Don't run all tests. Just run the right ones."**

---

## Who Uses It and How

### The User Journey

```
Developer changes some code
        ↓
Opens this tool in their browser
        ↓
Selects the repository and the branch with their changes
        ↓
Clicks "Select Tests"
        ↓
Sees a list of tests to run (usually takes 30–60 seconds)
        ↓
Runs only those tests — saves time!
```

### What the Interface Looks Like

The tool has a simple web page where you:

| Step | What You Do |
|------|-------------|
| 1 | Choose your **repository** (the project's code lives here on GitHub) |
| 2 | Choose the **source branch** (where your changes are) and the **target branch** (usually `main` or `develop`) |
| 3 | Click **"Select Tests"** |
| 4 | See the results: a table listing every test that should be run, with a label showing *why* it was selected |

---

## How It Works Behind the Scenes

The system uses **two approaches** together to find relevant tests. Think of them as two detectives working the same case.

### Detective 1 — The Structural Analyst (AST)

This detective looks at the **names** of things that changed.

- If you renamed a function called `getUserProfile`, it looks in the database for every test that mentions `getUserProfile`.
- It works like a phone book lookup: *"Who is connected to this name?"*
- It is **fast and precise** — but only works when names match exactly.

> **Limitation:** If you only changed a URL string from `/api/v1/users` to `/api/v2/users`, no *name* changed — only a value did. This detective finds nothing.

---

### Detective 2 — The Meaning Searcher (Semantic AI)

This detective understands **what things mean**, not just their names.

- It reads a plain-English summary of the code change.
- Then it searches through all test descriptions looking for ones that "sound related."
- It uses AI embeddings — a way to turn text into numbers so similar meanings get similar numbers.
- An AI model then reviews the results and keeps only the ones it judges **Critical** or **High** relevance.

**Example:**
- Code change summary: *"The payment checkout API path was updated."*
- Matching test found: *"should call the correct checkout endpoint"*

These two are related by meaning even though they share no exact words.

> **Limitation:** Sometimes it gets fooled by similar vocabulary. "favourites" and "wishlist" sound related but test completely different features.

---

### How the Two Work Together

```
Code Change
    │
    ├──── Detective 1 (AST) ─────────────────────────────────┐
    │     Finds tests by matching names in the database       │
    │                                                         │
    ├──── Detective 2 (Semantic AI) ─────────────────────────┤
    │     Finds tests by matching meaning via AI              │
    │     AI filters: keeps Critical + High relevance only    │
    │                                                         ▼
    │                                               Combine both lists
    │                                                         │
    └──────────────────────────────────────────────────────── ▼
                                                   Final Test List ✅
```

---

## Key Concepts Explained Simply

### What is a "Git Diff"?
A diff is simply the **difference between two versions of code**. Think of it like track-changes in a Word document — it shows exactly which lines were added, removed, or modified.

### What is a "Test"?
A test is a small program that checks whether a piece of code works correctly. For example: *"When I click the Login button with the right password, I should be taken to the home screen."* If the code is broken, the test fails.

### What is a "Repository"?
A repository (or "repo") is like a folder on GitHub where all the code for a project lives. It also stores the history of every change ever made.

### What is a "Branch"?
A branch is like a parallel version of the code. Developers make changes on a branch, test them, and then merge them into the main branch. This tool compares the developer's branch against the main branch to see what changed.

### What is the "Reverse Index"?
Think of it like a library card catalog. Instead of *"which books are in the library?"*, it answers *"which tests are related to this function/class/module?"* The system builds this catalog when you upload your test files.

### What are "Embeddings"?
Embeddings are a way to convert text into a list of numbers so that a computer can compare meanings. Two sentences with similar meanings get similar number lists. The system stores these in a vector database called Pinecone and uses them to find tests that are semantically similar to the code change.

---

## The Two Things You Need to Set Up

Before using the tool, two things need to be connected:

### 1. Source Repository (your production code)
This is your GitHub repository — the one with the code your developers are changing. You connect it by providing the GitHub URL and an access token.

### 2. Test Repository (your test files)
This is a ZIP file containing all your test files. You upload it to the system. The system then reads every test, builds the catalog, and stores embeddings in the AI database.

Once both are connected and linked, you are ready to click **"Select Tests"**.

---

## What the Results Show You

After clicking "Select Tests", you see a table like this:

| Test Name | Class / Group | Why Selected |
|-----------|---------------|--------------|
| `should call the checkout endpoint` | `CheckoutApi` | **AST** — exact name match |
| `should handle payment failure` | `PaymentReducer` | **Semantic** — meaning match |
| `verifies the cart total calculation` | `CartUtils` | **Both** — matched both ways |

Each test has a label:
- **AST** — found because a function/class name matched exactly
- **Semantic** — found because the meaning matched
- **Both** — found by both approaches (highest confidence)

You also see a **summary at the top**: Total tests selected, how many were AST matches, how many were Semantic matches.

---

## Known Limitations (What It Can't Do Yet)

No system is perfect. Here are the known gaps:

| Limitation | What It Means | How Bad? |
|------------|--------------|----------|
| Only string/value changed | If you changed a URL inside a config object (not a function name), the AST detective finds nothing | Low — AI search covers most cases |
| JavaScript import chains | The system doesn't yet trace "test file A imports from file B" for JavaScript. It can trace this for Python. | Medium — AI search partially covers it |
| Naming collisions | If `favourites` and `wishlist` both exist, changing one can accidentally match the other's tests | Low — LLM judge usually filters these out |
| New tests not embedded yet | If you add a brand new test but haven't re-run the analysis, it won't be considered | Low — run "Analyze" again to fix |

---

## Quick Glossary

| Word | Simple Meaning |
|------|---------------|
| Diff | The before-and-after of a code change |
| Test | A small program that checks if code works correctly |
| Repository | A folder on GitHub containing all project code |
| Branch | A parallel version of the code for making changes |
| AST | A way to understand code structure by looking at names |
| Semantic Search | Finding things by meaning, not exact words |
| LLM | A large AI language model (like GPT) that reads and understands text |
| Embeddings | Text converted to numbers so AI can compare meanings |
| Pinecone | The AI database that stores embeddings |
| Reverse Index | A lookup table: "which tests are related to this function?" |
| Co-location | When one test in a file is selected, pull in nearby tests from the same file |
| Threshold | A minimum score — tests below it are dropped as "not relevant enough" |

---

## Frequently Asked Questions

**Q: Do I need to understand code to use this tool?**
No. You just pick branches and click a button. The tool does all the work.

**Q: How long does it take?**
Usually **30 to 60 seconds**. The AI processing (Semantic search + classification) is the main time cost.

**Q: Is it 100% accurate?**
No tool is. It aims for ~90% precision (few false alarms) and ~95% recall (few missed tests). The remaining gap is covered by the two-detective approach cross-checking each other.

**Q: What if I think a test is missing from the results?**
Check if the test file has been uploaded and analyzed. Then check if the function/feature name in the test description matches anything in the changed code. If not, it may be a semantic gap — the AI didn't find the connection by meaning either.

**Q: Can it work with any programming language?**
Currently it fully supports **Python** and **JavaScript/TypeScript**. Java support is being added. It can read test files in any of these languages.

**Q: What if I upload new tests?**
Click "Analyze" on the test repository page to re-read all tests and rebuild the catalog. Then click "Regenerate Embeddings" to update the AI database.

---

*This guide was written for first-time users and stakeholders. For the full technical specification including APIs, architecture diagrams, and accuracy analysis, see [SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md).*
