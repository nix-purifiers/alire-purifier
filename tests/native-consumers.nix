{ pkgs, built }:
assert import ./native-eval.nix { inherit pkgs; };
pkgs.runCommand "alire-native-consumers"
  {
    nativeBuildInputs = [
      pkgs.gcc
      pkgs.patchelf
      (pkgs.python3.withPackages (p: [ p.cffi ]))
      pkgs.jdk25
    ];
  }
  ''
    set -euo pipefail
    mkdir -p "$out"
    trap 'for file in "$out"/*; do echo "$file" >&2; cat "$file" >&2; done' ERR
    export PYTHONPATH=${built.projections.python-ffi}
    prefix=$(python3 -c 'import json; print(json.load(open("${built.projections.native}/catalog.json"))["prefix"])')
    library="$prefix/lib/answer/libanswer.so"
    gcc -I "$prefix/include" ${./native/consumer.c} -ldl -o consumer
    ./consumer "$library" "$out/c.maps" > "$out/c.stdout" 2> "$out/c.stderr"
    for mode in ctypes cffi; do
      python3 ${./native/python-consumer.py} "$library" "$mode" "$out/$mode.maps" > "$out/$mode.stdout" 2> "$out/$mode.stderr"
    done
    cp ${./native/Consumer.java} Consumer.java
    javac Consumer.java
    java @${built.projections.java-ffi}/java.args --enable-native-access=ALL-UNNAMED Consumer "$library" "$out/java.maps" > "$out/java.stdout" 2> "$out/java.stderr"
    for name in c ctypes cffi java; do
      test ! -s "$out/$name.stderr"
      test "$(head -n 1 "$out/$name.stdout")" = 'Hello, world!'
      test "$(tail -n 1 "$out/$name.stdout")" = 'purifier finalized'
      test "$(wc -l < "$out/$name.stdout")" -eq 3
    done
    cp "$prefix/native-libraries.json" "$out/native-libraries.json"
    python3 ${./native/check-origins.py} "$prefix" "$out"
    python3 ${./native/missing-closure.py} "$prefix" "$out"
  ''
