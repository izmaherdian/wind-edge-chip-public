#!/usr/bin/env bash
# Publish a cleaned copy of main to the public repo (izmaherdian/wind-edge-chip-public).
#   scripts/publish_public.sh          # build, scan, push
#   scripts/publish_public.sh --dry    # build and scan only
# Paths in .public-exclude are dropped. Text in .public-redact (old==>new per line) is replaced,
# and files under .public-overrides/<path> replace <path> (e.g. a PDF rebuilt from redacted LaTeX). The tree and commit message are scanned for the
# patterns in .public-secrets-patterns (private-only) and for generic secrets; any hit aborts.
set -euo pipefail
URL=git@github.com:izmaherdian/wind-edge-chip-public.git
SRC=${SRC:-main}
cd "$(git rev-parse --show-toplevel)"
dry=0; [[ "${1:-}" == "--dry" ]] && dry=1

git fetch -q "$URL" main:refs/public/main 2>/dev/null || true
base=$(git rev-parse -q --verify refs/public/main || true)

idx=$(mktemp); trap 'rm -f "$idx"' EXIT
export GIT_INDEX_FILE=$idx
git read-tree "$SRC"
git show "$SRC:.public-exclude" > "$idx.ex"
git ls-files -c -i --exclude-from="$idx.ex" -z | xargs -0 -r git rm -q --cached --
rm -f "$idx.ex"
# Redact text
if git cat-file -e "$SRC:.public-redact" 2>/dev/null; then
  git show "$SRC:.public-redact" > "$idx.rd"
  olds=$(cut -d'=' -f1 "$idx.rd" | grep -v '^\s*$' | paste -sd'|')
  while IFS= read -r p; do
    mode=$(git ls-files -s -- "$p" | cut -d' ' -f1)
    new=$(git show ":$p" | python3 -c 'import sys
rules=[l.rstrip("\n").split("==>",1) for l in open(sys.argv[1]) if "==>" in l]
s=sys.stdin.read()
for a,b in rules: s=s.replace(a,b)
sys.stdout.write(s)' "$idx.rd" | git hash-object -w --stdin)
    git update-index --cacheinfo "$mode,$new,$p"
  done < <(git grep --cached -I -l -E "$olds")
  rm -f "$idx.rd"
fi
# Overrides
while IFS= read -r o; do
  p=${o#.public-overrides/}
  git update-index --add --cacheinfo "100644,$(git rev-parse "$SRC:$o"),$p"
done < <(git ls-tree -r --name-only "$SRC" .public-overrides/)
tree=$(git write-tree)
unset GIT_INDEX_FILE

# Safety scan
fail=0
if git cat-file -e "$SRC:.public-secrets-patterns" 2>/dev/null; then
  pats=$(git show "$SRC:.public-secrets-patterns" | grep -v '^\s*$' | paste -sd'|')
  if git grep -I -l -E "$pats" "$tree" >/dev/null; then
    echo "ABORT: private pattern in text files:"; git grep -I -l -E "$pats" "$tree"; fail=1; fi
  tmp=$(mktemp)
  while IFS= read -r p; do
    git cat-file -p "$tree:$p" > "$tmp"
    case "$p" in
      *.pdf) t=$(pdftotext -q "$tmp" - 2>/dev/null || true);;
      *.pptx|*.docx|*.xlsx) t=$(unzip -p "$tmp" 2>/dev/null | tr -d '\0' || true);;
    esac
    if grep -q -E "$pats" <<<"$t"; then echo "ABORT: private pattern in $p"; fail=1; fi
  done < <(git ls-tree -r --name-only "$tree" | grep -E '\.(pdf|pptx|docx|xlsx)$')
  rm -f "$tmp"
fi
if git grep -I -l -E '(ghp_[A-Za-z0-9]{30,}|github[_]pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|BEGIN [A-Z ]*PRIVATE KEY)' "$tree" >/dev/null; then
  echo "ABORT: generic secret pattern found"; fail=1; fi
[[ $fail == 0 ]] || exit 1

if [[ -n "$base" && "$(git rev-parse "$base^{tree}")" == "$tree" ]]; then
  echo "Public repo already up to date."; exit 0; fi
msg="Sync from private main $(git rev-parse --short "$SRC")"
commit=$(git commit-tree "$tree" ${base:+-p "$base"} -m "$msg")
echo "Public commit $commit ($(git ls-tree -r --name-only "$tree" | wc -l) files)"
if [[ $dry == 1 ]]; then echo "Dry run: not pushed."; exit 0; fi
git push "$URL" "$commit:refs/heads/main"
git update-ref refs/public/main "$commit"
