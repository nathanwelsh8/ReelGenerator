#!/bin/bash
# Patch ImageMagick policy.xml to allow @* paths (needed for MoviePy/TextClip)

set -e

# Find all policy.xml files and comment out the problematic line
find /etc -type f -name 'policy.xml' | while read -r file; do
    if grep -q '<policy domain="path" rights="none" pattern="@\*"' "$file"; then
        echo "Patching $file ..."
        sed -i 's|^\([[:space:]]*\)<policy domain="path" rights="none" pattern="@\*"[[:space:]]*/>|<!-- \1<policy domain="path" rights="none" pattern="@*" /> -->|' "$file"
    fi
done

echo "✅ ImageMagick policy.xml patch complete."
