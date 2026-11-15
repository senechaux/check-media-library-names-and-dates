"""Solo temporales sintéticos; los clientes remotos de las pruebas son simulados."""

import json

from media_library.config import load_config
from video_support import configure_video, run_real, manifest, video_tools, exiftool, make_video


def configure_export(config_file,tool,*,video=False,metadata=False,manual=False,reviewed=True,**options):
    configure_video(config_file,tool)
    raw=config_file.read_text().replace('normalize="auto"','normalize="disabled"').replace('compression="auto"','compression="disabled"')
    if video:
        raw=raw.replace('normalize="disabled"','normalize="auto"').replace('compression="disabled"','compression="auto"')
    if metadata:raw=raw.replace('metadata="disabled"','metadata="auto"')
    raw=raw.replace('export="disabled"','export="manual"' if manual else 'export="auto"').replace('audit="disabled"','audit="auto"')
    raw+='\n[export]\n'
    raw+='\n'.join(f'{key}={json.dumps(value)}' for key,value in {"video_quality_reviewed":reviewed,**options}.items())+'\n'
    config_file.write_text(raw)
    return load_config(config_file)


def make_jpeg(path,*,orientation=1,exif=False,size=(100,60)):
    import pytest
    Image=pytest.importorskip('PIL.Image',reason='Falta Pillow real: instalar extra images')
    path.parent.mkdir(parents=True,exist_ok=True)
    image=Image.new('RGB',size,'red');image.paste('blue',(size[0]//2,0,*size))
    tags=Image.Exif()
    if exif:tags[274]=orientation
    image.save(path,exif=tags if exif else b'')
