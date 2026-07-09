# modify_core.py - Add auto web search to _execute_task_logic
lines = open(r'D:\桌面\quant_backtest\automation\core.py', 'r', encoding='utf-8').readlines()

# Find line 294 (after "return error no strategy")
# Insert auto web search logic there
insert_idx = 294  # Line 295 in 1-indexed

new_lines = [
    '\n',
    '        # AUTO WEB SEARCH: triggered when task needs latest context\n',
    '        if self._should_auto_search(task):\n',
    '            search_query = self._extract_search_query(task)\n',
    '            if search_query:\n',
    '                logger.info(f"[AUTO] Web search for task " + str(task.id) + ": " + search_query)\n',
    '                search_result = await self.web_search.search(search_query, n=3)\n',
    '                if search_result.results:\n',
    '                    context = self._format_search_results_auto(search_result)\n',
    '                    task.instruction = task.instruction + "\\n\\n[Web Context:]\\n" + context\n',
    '                    logger.info("[AUTO] Enhanced task with " + str(len(search_result.results)) + " search result(s)")\n',
    '\n',
]

# Insert at the right position
lines = lines[:insert_idx] + new_lines + lines[insert_idx:]

# Now add helper methods after _execute_task_logic (after line 322+)
# Find the line after "return success..."
for i, line in enumerate(lines):
    if 'return {"success": True, "action": action, "score": eval_resul' in line:
        # Insert helper methods after this
        helper_methods = '''
    def _should_auto_search(self, task: Task) -> bool:
        triggers = ["latest", "recent", "current", "new", "update", "news", "today", "now"]
        return any(t in task.instruction.lower() for t in triggers)

    def _extract_search_query(self, task: Task) -> str:
        words = [w for w in task.instruction.split() if len(w) > 3][:5]
        return " ".join(words)

    def _format_search_results_auto(self, response) -> str:
        items = [f"- {r.title}: {r.snippet[:80]}" for r in response.results[:3]]
        return chr(10).join(items)

'''
        lines.insert(i+2, helper_methods)
        break

open(r'D:\桌面\quant_backtest\automation\core.py', 'w', encoding='utf-8').writelines(lines)
print('OK: core.py modified with auto web search')
