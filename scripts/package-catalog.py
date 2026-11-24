#!/usr/bin/env python3
"""Collect the nine validated firmware profiles into one documented bundle."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def assemble(destination=None):
    groups = [('universal', ROOT/'artifacts/variants'), ('4m', ROOT/'artifacts/4m')]
    records=[]
    for group,base in groups:
        entries=json.loads((base/'manifest.json').read_text())
        expected=6 if group=='universal' else 3
        if len(entries)!=expected:
            raise ValueError(f'Expected {expected} entries in {group}')
        for item in entries:
            if item['tracked_source_dirty']:
                raise ValueError('Refusing firmware built from a dirty tracked source tree')
            records.append((group,base,item))
    commits={item['source_commit'] for _,_,item in records}
    if len(commits)!=1:
        raise ValueError('All firmware must come from the same source commit')
    commit=commits.pop()
    destination=Path(destination) if destination else ROOT/'artifacts/catalog'/f'W9YBZ-firmware-{commit[:7]}'
    if destination.exists():
        raise FileExistsError(f'Output exists; choose a new --output directory: {destination}')
    # Check all inputs before creating the bundle.
    for group,base,item in records:
        source=base/item['profile']/item['language']
        if hashlib.sha256((source/item['firmware']).read_bytes()).hexdigest()!=item['sha256']:
            raise ValueError(f'Firmware hash mismatch: {item["firmware"]}')
        if group=='4m':
            asset_dir=source/'eeprom-assets'
            resource_manifest=json.loads((asset_dir/'resources.json').read_text())
            if resource_manifest['firmware_version']!=item['firmware'].removesuffix('.bin'):
                raise ValueError('Resource/firmware version mismatch')
            for record in resource_manifest['resources']:
                blob=(asset_dir/record['file']).read_bytes()
                if len(blob)!=record['length'] or hashlib.sha256(blob).hexdigest()!=record['sha256']:
                    raise ValueError('Resource hash mismatch')
    destination.mkdir(parents=True)
    listing=[]
    for group,base,item in records:
        relative=Path(group)/item['profile']/item['language']
        source=base/item['profile']/item['language']
        target=destination/relative
        target.mkdir(parents=True)
        for name in (item['firmware'],'manifest.json','compiler-flags.txt'):
            shutil.copy2(source/name,target/name)
        if group=='4m':
            shutil.copytree(source/'eeprom-assets',target/'eeprom-assets')
        listing.append(dict(group=group,path=str(relative/item['firmware']),**item))
    (destination/'manifest.json').write_text(json.dumps(listing,ensure_ascii=False,indent=2)+'\n')
    for name in ('radio-4m.py','eeprom-4m-assets.py'):
        shutil.copy2(ROOT/'scripts'/name,destination/'4m'/name)
    catalog=(ROOT/'doc/FIRMWARE_CATALOG.md').read_text().replace('`bf9dfae`',f'`{commit[:7]}`')
    (destination/'README.md').write_text(catalog)
    docs=destination/'docs';docs.mkdir()
    for name in ('FIRMWARE_VARIANTS.md','FIRMWARE_4M.md'):
        shutil.copy2(ROOT/'doc'/name,docs/name)
    instructions=(ROOT/'doc/FIRMWARE_4M.md').read_text().replace('](FIRMWARE_VARIANTS.md)','](../docs/FIRMWARE_VARIANTS.md)')
    (destination/'4m/README.md').write_text(instructions)
    sums=[]
    for file in sorted(destination.rglob('*')):
        if file.is_file():
            sums.append(f'{hashlib.sha256(file.read_bytes()).hexdigest()}  {file.relative_to(destination).as_posix()}\n')
    (destination/'SHA256SUMS.txt').write_text(''.join(sums))
    archive=destination.with_suffix('.zip')
    if archive.exists():
        raise FileExistsError(archive)
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for file in sorted(destination.rglob('*')):
            if file.is_file():
                z.write(file,file.relative_to(destination).as_posix())
    archive.with_name(archive.name+'.sha256').write_text(f'{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n')
    print(f'Collected 9 firmware images, matching 4M resources, tools, docs and hashes: {archive}')
    return archive

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    assemble(args.output)
