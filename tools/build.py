"""Repack 任我行 so it installs on current Android, then align and sign it.

The app is hardened with 360 jiagu: classes.dex only contains the packer stub
and the real code sits encrypted inside it. Nothing here touches code or
resources. The only edit is the compiled android:targetSdkVersion value in
AndroidManifest.xml (22 -> 24), because Android 15+ refuses to install
anything targeting below API 24.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import axml

DROP_PREFIX = 'META-INF/'
DROP_SUFFIX = ('.SF', '.RSA', '.DSA', '.MF')


def patch_apk(src, dst, target_sdk):
    with zipfile.ZipFile(src) as zin:
        manifest = zin.read('AndroidManifest.xml')
        patched, old = axml.patch_target_sdk(manifest, target_sdk)
        if old == target_sdk:
            raise SystemExit('source already targets SDK %d' % target_sdk)
        with zipfile.ZipFile(dst, 'w') as zout:
            for info in zin.infolist():
                name = info.filename
                if name.startswith(DROP_PREFIX) and name.upper().endswith(DROP_SUFFIX):
                    continue
                data = patched if name == 'AndroidManifest.xml' else zin.read(name)
                out = zipfile.ZipInfo(name, date_time=info.date_time)
                out.compress_type = info.compress_type
                out.external_attr = info.external_attr
                out.create_system = info.create_system
                zout.writestr(out, data)
    return old


def run(cmd):
    print('+', ' '.join(cmd))
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--build-tools', required=True)
    ap.add_argument('--keystore', required=True)
    ap.add_argument('--ks-pass', required=True)
    ap.add_argument('--key-alias', required=True)
    ap.add_argument('--key-pass', required=True)
    ap.add_argument('--target-sdk', type=int, default=24)
    ap.add_argument('--version-name', default=None)
    args = ap.parse_args()

    bt = os.path.abspath(args.build_tools)
    exe = '.exe' if os.name == 'nt' else ''
    zipalign = os.path.join(bt, 'zipalign' + exe)
    # Call the jar directly: the wrapper script resolves its own path, which
    # breaks when build-tools is referenced relatively.
    apksigner = ['java', '-jar', os.path.join(bt, 'lib', 'apksigner.jar')]

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    work = tempfile.mkdtemp(prefix='rwx-')
    try:
        unsigned = os.path.join(work, 'unsigned.apk')
        aligned = os.path.join(work, 'aligned.apk')

        old = patch_apk(args.input, unsigned, args.target_sdk)
        print('targetSdkVersion: %d -> %d' % (old, args.target_sdk))

        run([zipalign, '-p', '-f', '4', unsigned, aligned])
        run(apksigner + ['sign',
             '--ks', args.keystore,
             '--ks-pass', 'pass:' + args.ks_pass,
             '--key-pass', 'pass:' + args.key_pass,
             '--ks-key-alias', args.key_alias,
             '--v1-signing-enabled', 'true',
             '--v2-signing-enabled', 'true',
             '--v3-signing-enabled', 'true',
             '--min-sdk-version', '14',
             '--out', args.output, aligned])
        run(apksigner + ['verify', '--verbose', '--print-certs', args.output])
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print('\nbuilt:', args.output, '(%d bytes)' % os.path.getsize(args.output))


if __name__ == '__main__':
    main()
