#!/bin/bash
TO=$(command -v gtimeout || command -v timeout)
for t in tareas/*.md; do
  b=$(basename "$t" .md)
  echo ">>> $t"
  $TO 600 aider --yes-always --no-show-model-warnings \
    --model ollama_chat/qwen2.5-coder:3b \
    --map-tokens 0 --timeout 300 \
    --message-file "$t" \
    $(cat "tareas/$b.files") \
    < /dev/null 2>&1 | tee "logs/$b.log"
done
