#!/usr/bin/env python3
"""Test di tools/vivi.py (G1 B4): comando dentro il wrapper zsh, processo claude, id dei task dalle trascrizioni.

Lancio:  python3 -m unittest discover -s tests -v     (dalla radice di superagent-method)
"""
import importlib.util, json, os, shutil, tempfile, unittest

QUI = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("vivi", os.path.join(QUI, "..", "tools", "vivi.py"))
vivi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vivi)

WRAP = ("/bin/zsh -c source /x/snapshot.sh 2>/dev/null || true && setopt NO_EXTENDED_GLOB 2>/dev/null || true && "
        "eval 'cd \"$HOME/hub\" && tail -n0 -F coda.jsonl | grep --line-buffered '\"'\"'\"sveglia\": true'\"'\"'' "
        "< /dev/null && pwd -P >| /tmp/claude-1-cwd")


class Vivi(unittest.TestCase):
    def test_comando_eval(self):
        self.assertEqual(vivi.comando_eval(WRAP),
                         "cd \"$HOME/hub\" && tail -n0 -F coda.jsonl | grep --line-buffered '\"sveglia\": true'")
        self.assertIsNone(vivi.comando_eval("/usr/bin/caffeinate -i"))

    def test_e_claude(self):
        self.assertTrue(vivi.e_claude("claude -n METODO"))
        self.assertTrue(vivi.e_claude("/Users/x/.local/share/claude/versions/2.1.319 --x"))
        self.assertTrue(vivi.e_claude("2.1.319"))
        self.assertFalse(vivi.e_claude("ugrep -G --line-buffered x"))
        self.assertFalse(vivi.e_claude("/bin/zsh -c x"))
        self.assertFalse(vivi.e_claude(""))

    def test_id_dei_task(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        f = os.path.join(d, "s.jsonl")
        voci = [
            {"message": {"content": [{"type": "tool_use", "id": "u1", "name": "Monitor",
                                      "input": {"command": "tail -F a", "description": "coda"}}]}},
            {"message": {"content": [{"type": "tool_result", "tool_use_id": "u1",
                                      "content": "Monitor started (task bAAA1, expires in 30m)"}]}},
            {"message": {"content": [{"type": "tool_use", "id": "u2", "name": "Bash",
                                      "input": {"command": "sleep 900", "run_in_background": True}}]}},
            {"message": {"content": [{"type": "tool_result", "tool_use_id": "u2",
                                      "content": [{"type": "text", "text": "Command running in background with ID: bBBB2. Output…"}]}]}},
            {"message": {"content": [{"type": "tool_use", "id": "u3", "name": "Bash", "input": {"command": "ls"}}]}},
            {"message": {"content": [{"type": "tool_use", "id": "u4", "name": "Monitor",
                                      "input": {"command": "tail -F a", "description": "coda"}}]}},
            {"message": {"content": [{"type": "tool_result", "tool_use_id": "u4",
                                      "content": "Monitor started (task bCCC3, expires in 30m)"}]}},
        ]
        with open(f, "w") as h:
            h.write("".join(json.dumps(v) + "\n" for v in voci))
        m = vivi.id_dei_task([f])
        self.assertEqual(m["tail -F a"], ("Monitor", "bCCC3", "coda"))   # riarmato: vale l'ultimo id
        self.assertEqual(m["sleep 900"], ("Bash", "bBBB2", ""))
        self.assertNotIn("ls", m)

    def test_testo(self):
        t = vivi.testo([{"pid": 1, "kind": "Monitor", "id": "bX", "description": "coda", "command": "tail -F a"},
                        {"pid": 2, "kind": "?", "id": None, "description": "", "command": "sleep 9"}])
        self.assertIn("Monitor bX «coda»: tail -F a", t)
        self.assertIn("background task (id unknown): sleep 9", t)


if __name__ == "__main__":
    unittest.main()
