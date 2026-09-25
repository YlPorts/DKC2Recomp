#!/usr/bin/env python3
"""Materialize an isolated DKC2 Android source workspace from audited Git pins.

Without --rom this prepares SOURCE ONLY. It never substitutes an interpreter-only
APK or a placeholder game for missing generated cartridge code. ROM input is
local-only and is neither downloaded nor uploaded by this program.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

DKC2 = "e181419f2f8ff7b12494453e74840a4828bdb723"
DKC1_ANDROID = "e6cde9c43fc6a4d49c7eae5edba93b5bf2f5dea0"
ENGINE = "fe6045c22bb023e15d825ec40bfc25387ec9253c"
OLD_ENGINE = "851b11e38588818afc705e4270d3eb982b7b2af2"
OLD_BASE = "cb4dae77a6552790cbb7a9663957b2cb6c3e6b58"
OLD_ROM = "fa8cacf5bbfc39ee6bbaa557adf89133d60d42f6cf9e1db30d5a36a469f74d15"
ROM_SHA256 = "35421a9af9dd011b40b91f792192af9f99c93201d8d394026bdfb42cbf2d8633"
ROM_SIZE = 4194304
HERE = Path(__file__).resolve().parent
TEXT_SUFFIXES = {".c", ".h", ".java", ".py", ".gradle", ".xml", ".properties", ".bat", ".sh"}
# Fail closed if the upstream files used by the structural edits differ.
EXPECTED_BLOBS = {
    "android/native/android_host.c": "b067aa1ef31f2e5bcd67cde23f8199503745e101",
    "android/native/CMakeLists.txt": "72127f85eaff5c5c97d8b7cc52cedbb8641649a2",
    "android/tools/build_android.py": "ae684bb08052d69c45d861b94bb69a5883b9f60a",
    "android/app/build.gradle": "303fcd4287a0a307354ce80d18f7a7e5fae48adc",
    "android/app/src/main/java/com/ylports/dkc1recomp/AppSettings.java": "1d2cc972144d48a8b03d4f7eb99f4c25cd34beeb",
    "android/app/src/main/java/com/ylports/dkc1recomp/OptionsPanel.java": "ea1195c6554fc9a9b6d25b7baa10938fa7ad62b5",
}


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def verify_rom(path: Path) -> str:
    with path.open("rb") as stream:
        raw = stream.read(ROM_SIZE + 513)
    if len(raw) == ROM_SIZE + 512:
        raw = raw[512:]
    if len(raw) != ROM_SIZE:
        raise ValueError("Se necesita DKC2 USA v1.0 de 4 MiB, con o sin cabecera de 512 bytes; no ZIP.")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != ROM_SHA256:
        raise ValueError(f"ROM no compatible. SHA-256 recibido: {digest}; esperado: {ROM_SHA256}")
    return digest


def run(args: list[str], cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def checkout(url: str, pin: str, target: Path) -> None:
    if target.exists():
        raise FileExistsError(f"El destino ya existe; no se sobrescribe: {target}")
    target.mkdir(parents=True)
    run(["git", "init", str(target)])
    run(["git", "remote", "add", "origin", url], target)
    run(["git", "fetch", "--depth", "1", "origin", pin], target)
    run(["git", "checkout", "--detach", "FETCH_HEAD"], target)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=target, text=True).strip()
    if head != pin:
        raise RuntimeError("El checkout no coincide con la revisión fijada.")


def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"Contrato de migración cambiado: se esperaba una coincidencia de {old[:85]!r}")
    return text.replace(old, new, 1)


def between(text: str, start: str, end: str, replacement: str) -> str:
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError(f"Límites de migración ausentes o ambiguos: {start!r} / {end!r}")
    a, b = text.index(start), text.index(end)
    if b <= a:
        raise ValueError("Límites de migración invertidos.")
    return text[:a] + replacement + text[b:]


def rename_game(text: str) -> str:
    for old, new in [("DKC1", "DKC2"), ("Dkc1", "Dkc2"), ("dkc1", "dkc2"),
                     (OLD_ROM, ROM_SHA256), (OLD_ENGINE, ENGINE), (OLD_BASE, DKC2)]:
        text = text.replace(old, new)
    return text


def adapt_host(text: str) -> str:
    text = rename_game(text)
    text = once(text, '#include "dkc2_baby_kong.h"\n', '')
    text = once(text, '    Dkc2VideoSetEdgePolicy((Dkc2EdgePolicy)atomic_load(&s_options[OPT_EDGE]));\n', '')
    text = once(text, '    if(Dkc2BabyKongReady())Dkc2BabyKongSetEnabled(atomic_load(&s_options[OPT_BABY])!=0);\n', '')
    text = between(text, '  /* Keep speculative upstream widescreen switches off.',
                   '  (void)mkdir("tier2",0700);',
                   '  /* DKC2 uses its own reviewed terrain and object adapters. */\n')
    text = between(text, '  const int ultrawide=aspect',
                   '  if(!SnesInit(rom,(int)rom_size))',
                   '  Dkc2VideoSetWidescreen(aspect && !strcmp(aspect,"16:9"));\n'
                   '  RtlRegisterGame(Dkc2GameInfo());\n')
    text = between(text, '  s_aspect_key=ultrawide?',
                   '  const char *resume=Argument(argc,argv,"--resume");',
                   '  s_aspect_key=Dkc2VideoIsWidescreen()?"16x9":"4x3";\n')
    # Keep option-array ABI with the reused Java frontend, but reserve removed options.
    text = text.replace('OPT_EDGE', 'OPT_RESERVED_EDGE').replace('OPT_BABY', 'OPT_RESERVED_BABY')
    text = text.replace('ANDROID_ULTRAWIDE_EXTRA=96, ANDROID_MAX_WIDTH=256+2*ANDROID_ULTRAWIDE_EXTRA',
                        'ANDROID_MAX_WIDTH=kDkc2VideoWidescreenWidth')
    text = text.replace('s_filtered[448*224*4]', 's_filtered[kDkc2VideoWidescreenWidth*kDkc2VideoHeight*4]')
    text = text.replace('android-0.3.0-dev base=cb4dae77', 'android-0.1.0-dev base=e181419f')
    text = text.replace('v0.3.0-dev', 'v0.1.0-dev')
    for forbidden in ('BabyKong', 'dkc2_baby', 'VideoSetAspect', 'VideoGetAspect',
                      'VideoSetRom', 'VideoSetEdgePolicy', 'ultrawide', 'DKC2_WS_WALL'):
        if forbidden in text:
            raise ValueError(f"Quedó una dependencia de DKC1 en el host: {forbidden}")
    return text


def adapt_settings(text: str) -> str:
    text = rename_game(text)
    text = once(text, 'ASPECTS={"4:3","16:10","16:9","21:9"}', 'ASPECTS={"4:3","16:9"}')
    return once(text, 'get("aspect",0,0,3)', 'get("aspect",0,0,ASPECTS.length-1)')


def adapt_options(text: str) -> str:
    text = rename_game(text)
    text = once(text, '"Extras","Créditos"', '"Mods"')
    text = once(text, '"16:10 · experimental","16:9 · experimental","21:9 · ultrawide experimental"',
                '"16:9 · experimental"')
    text = between(text, '        LinearLayout edge=card(', '    private void audio(){', '    }\n')
    text = between(text, '        LinearLayout mod=card("Baby Kong', '        LinearLayout d=card(',
                   '        LinearLayout mod=card("Mods", "Los mods de DKC1 no son compatibles con DKC2. '
                   'La carga de mods de DKC2 aún no está integrada en esta primera adaptación.");\n')
    text = text.replace('"Donkey Kong Country"', '"Donkey Kong Country 2"')
    text = text.replace('"DKC2Recomp",20', '"DKC2 Android",20')
    text = text.replace('ANDROID  /  0.3.0-dev', 'ANDROID  /  0.1.0-dev')
    return text


def materialize(frontend: Path, output: Path) -> None:
    for rel, expected in EXPECTED_BLOBS.items():
        if git_blob((frontend/rel).read_bytes()) != expected:
            raise ValueError(f"El archivo de origen no coincide con el pin revisado: {rel}")
    android = output/'android'
    if android.exists():
        raise FileExistsError("El checkout DKC2 ya tiene android/; no se sobrescribe.")
    # Preserve all source licensing; discard old validation reports, not source dependencies.
    shutil.copytree(frontend/'android', android,
                    ignore=shutil.ignore_patterns('tests', 'BUILD_V0_3.json', 'VALIDACION_ACTUAL.md',
                                                 'third_party', '.gradle', '.cxx', 'build', '__pycache__'))
    for path in android.rglob('*'):
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            path.write_text(rename_game(path.read_text(encoding='utf-8')), encoding='utf-8')
    java = android/'app/src/main/java/com/ylports'
    (java/'dkc1recomp').rename(java/'dkc2recomp')
    sources = frontend/'android/app/src/main/java/com/ylports/dkc1recomp'
    (java/'dkc2recomp/AppSettings.java').write_text(adapt_settings((sources/'AppSettings.java').read_text()), encoding='utf-8')
    (java/'dkc2recomp/OptionsPanel.java').write_text(adapt_options((sources/'OptionsPanel.java').read_text()), encoding='utf-8')
    (android/'native/android_host.c').write_text(adapt_host((frontend/'android/native/android_host.c').read_text()), encoding='utf-8')
    # These are host-only pacing / presentation helpers, NOT DKC1 game routines.
    for name in ('desktop_audio_rate.c', 'desktop_audio_rate.h', 'desktop_filter.c', 'desktop_filter.h'):
        (android/'native'/name).write_text(rename_game((frontend/'runner'/name).read_text()), encoding='utf-8')
    shutil.copy2(HERE/'CMakeLists.txt', android/'native/CMakeLists.txt')
    build = android/'app/build.gradle'
    text = once(build.read_text(), 'versionCode 3', 'versionCode 1')
    text = once(text, "versionName '0.3.0-dev'", "versionName '0.1.0-dev'")
    # Preserve DKC1's attribution for borrowed host helpers, alongside DKC2's own license.
    text = once(text, "    from('../LICENSE')", "    from('../upstream-notices') { into 'dkc1-android-origin' }\n    from('../LICENSE')")
    build.write_text(text, encoding='utf-8')
    notices = android/'upstream-notices'; notices.mkdir()
    for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md'):
        shutil.copy2(frontend/name, notices/name)
    shutil.copy2(HERE/'README.md', android/'README.md')
    status = {'status': 'source-prepared-not-a-playable-apk', 'dkc2_commit': DKC2,
              'frontend_commit': DKC1_ANDROID, 'snesrecomp_commit': ENGINE,
              'rom_sha256': ROM_SHA256, 'application_id': 'com.ylports.dkc2recomp.mobile',
              'rom_bundled': False, 'generated_game_code_bundled': False,
              'android_execution_tested': False, 'whole_game_widescreen_verified': False}
    (android/'PORT_STATUS.json').write_text(json.dumps(status, indent=2)+'\n')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New directory; existing directories are never replaced')
    parser.add_argument('--rom', type=Path, help='Your local DKC2 USA v1.0 .sfc/.smc, never uploaded')
    parser.add_argument('--build', action='store_true', help='Generate native game code and invoke Gradle; requires --rom and Android SDK')
    parser.add_argument('--sdk', type=Path)
    parser.add_argument('--dependencies', action='store_true', help='Also prepare pinned snesrecomp and SDL2 for source checks')
    args = parser.parse_args()
    if args.build and not args.rom:
        parser.error('--build necesita --rom. No se compila un juego vacío.')
    if args.rom:
        args.rom = args.rom.expanduser().resolve(strict=True)
        verify_rom(args.rom)
    output = args.output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f'El destino ya existe; no se sobrescribe: {output}')
    if not shutil.which('git'):
        raise RuntimeError('Se necesita Git en PATH.')
    # The entire transformation is staged; failed preparation never presents a completed workspace.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='dkc2-android-stage-', dir=output.parent) as temporary:
        stage = Path(temporary)
        frontend, game = stage/'frontend', stage/'game'
        checkout('https://github.com/YlPorts/DKC1Recomp-ANdroid.git', DKC1_ANDROID, frontend)
        checkout('https://github.com/YlPorts/DKC2Recomp.git', DKC2, game)
        materialize(frontend, game)
        game.rename(output)
    if args.dependencies:
        path = output/'android/tools/build_android.py'
        spec = importlib.util.spec_from_file_location('dkc2_android_builder', path)
        if spec is None or spec.loader is None:
            raise RuntimeError('No se pudo cargar el preparador de dependencias.')
        builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
        builder.prepare_dependencies()
    if args.rom:
        command = [sys.executable, str(output/'android/tools/build_android.py'), '--rom', str(args.rom)]
        if not args.build: command.append('--prepare-only')
        if args.sdk: command += ['--sdk', str(args.sdk.expanduser().resolve())]
        run(command, output)
    print(f'Fuentes Android preparadas en: {output}')
    if not args.build:
        print('No se ha construido un APK jugable. Falta generación/compilación y prueba en Android.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(1)
