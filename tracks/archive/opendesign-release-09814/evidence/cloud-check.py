#!/usr/bin/env python3
"""Check the whole CI run and record every Windows assertion, not artifact presence."""
import json, re, subprocess, sys
RUN = "36226326190"
SHA = "b37b8ddd4c3be2f35fccf6c8a853caab3036bd0f"
REPO = "SunJ1ayu/OpenDesign"
def gh(*args):
    return subprocess.check_output(["gh", *args, "--repo", REPO], text=True)
r = json.loads(gh("run", "view", RUN, "--json", "status,conclusion,headSha,jobs,url"))
assert r["headSha"] == SHA, r["headSha"]
assert r["status"] == "completed" and r["conclusion"] == "success", r["status"] + ":" + r["conclusion"]
assert {j["name"] for j in r["jobs"]} == {"payload", "e2e"}
for j in r["jobs"]:
    assert j["conclusion"] == "success", j["name"]
    print("OK job", j["name"], j["conclusion"])
log = gh("run", "view", RUN, "--log")
checks = []
for line in log.splitlines():
    # GitHub prepends job / step / UTC timestamp. Only actual assertion output counts.
    match = re.search(r"\d{4}-\d{2}-\d{2}T\S+\s+(OK|FAIL)\s+(.*)", line)
    if match:
        checks.append((match.group(1), match.group(2)))
        print(match.group(1), match.group(2))
assert checks, "No Windows assertion output found"
failed = [text for verdict, text in checks if verdict == "FAIL"]
assert not failed, failed
for section in ["E1.", "E1r.", "E2.", "E3.", "E4.", "E5.", "E6.", "E7."]:
    assert any(text.startswith(section) for verdict, text in checks), "Missing " + section
print("OK run", RUN, "head", SHA, "assertions", len(checks), "FAIL", len(failed), r["url"])
