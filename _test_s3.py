"""Test Scenario 3 end-to-end."""
import sys, os
sys.path.insert(0, ".")
os.environ.setdefault("PYTHONPATH", ".")

from git_diff_processor.process_diff_programmatic import process_diff_and_select_tests

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

import asyncio

result = asyncio.run(process_diff_and_select_tests(
    diff_content=DIFF,
    schema_name="test_repo_261b672a",
    semantic_config={}
))

selected = result.get("tests", [])
print(f"\nTotal selected: {len(selected)}")
print(f"AST matches:      {result.get('ast_matches', 0)}")
print(f"Semantic matches: {result.get('semantic_matches', 0)}")
print()
print(f"{'Test ID':<12} {'Match':<8} {'Sim':>6} {'Conf':>6}  Test Name")
print("-" * 90)

def get_test_name(t):
    class_name = t.get('class_name') or ''
    method_name = t.get('method_name') or ''
    # method_name already includes class_name context (e.g. "ClassName > it name")
    # Avoid duplication: if method_name starts with class_name, just use method_name
    if method_name and class_name and method_name.startswith(class_name):
        return method_name
    if class_name and method_name:
        return f"{class_name} > {method_name}"
    return method_name or class_name or t.get('test_id', '')

for t in sorted(selected, key=lambda x: x['test_id']):
    sim = f"{t.get('similarity',0)*100:.0f}%" if t.get('similarity') else "-"
    name = get_test_name(t)[:65]
    print(f"{t['test_id']:<12} {t.get('match_type',''):<8} {sim:>6} {t.get('confidence',''):>6}  {name}")

print()
expected_critical = {
    "capitalizeFirstLetter with checkWhiteSpace > capitalizes the first letter of each word",
    "capitalizeFirstLetter with checkWhiteSpace > capitalizes a single word",
    "capitalizeFirstLetter with checkWhiteSpace > returns undefined",
    "toastReducer",
}
print("Expected CRITICAL tests (7 total):")
print("  3 × capitalizeFirstLetter tests in auth-storage.cross.test.js")
print("  4 × toastReducer tests in favourites-watchlist.feature.test.js")
print()
print("Expected HIGH tests (21 total):")
print("  10 × utilities.pure.test.js sibling tests")
print("  7  × isUserLoggedIn/updateNewTokenDetails/generateCardNumber in auth-storage")
print("  4  × favouritesReducer in favourites-watchlist.feature.test.js")
