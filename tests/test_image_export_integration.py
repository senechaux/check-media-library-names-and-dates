"""Pillow/ExifTool/FFmpeg reales; JPEG sintéticos, nunca fotografías personales."""

from dataclasses import replace

import pytest

from media_library.capture_dates import parse_date
from media_library.config import Tool
from media_library.date_settings import parse_date_settings
from media_library.image_export import inspect_image, render_image, validate_image
from media_library.export_settings import parse_export_settings
from media_library.video_driver import VideoDriver
from metadata_support import exiftool

pytestmark=pytest.mark.integration


@pytest.mark.parametrize("orientation",[1,6,8])
def test_real_jpeg_orientation_icc_dimensions_and_capture_date(config,tmp_path,exiftool,orientation):
    Image=pytest.importorskip("PIL.Image",reason="Falta Pillow real: instalar extra images")
    ImageCms=pytest.importorskip("PIL.ImageCms",reason="Falta soporte ICC real")
    source=tmp_path/'source.jpg';output=tmp_path/'output.jpg'
    image=Image.new('RGB',(2000,1000),'red');image.paste('blue',(1000,0,2000,1000))
    tags=Image.Exif();tags[274]=orientation
    icc=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    image.save(source,quality=95,exif=tags,icc_profile=icc)
    settings=parse_export_settings({})
    expected=inspect_image(source,1200)
    render_image(source,output,settings)
    config=replace(config,tools={"exiftool":Tool(exiftool.executable)})
    driver=VideoDriver(config)
    from dataclasses import asdict
    date=asdict(parse_date('2026-01-02T03:04:05+01:00','user'))
    evidence=driver.restore_dates(output,date,parse_date_settings({}),driver.dates.read(source))
    assert validate_image(output,expected)["orientation"]==1
    with Image.open(output) as rendered:
        assert rendered.size==((1200,600) if orientation==1 else (600,1200))
        assert rendered.info['icc_profile']==icc
        if orientation==6:
            assert rendered.getpixel((300,100))[0]>200 and rendered.getpixel((300,1100))[2]>200
        if orientation==8:
            assert rendered.getpixel((300,100))[2]>200 and rendered.getpixel((300,1100))[0]>200
    assert evidence['targets']['ExifIFD:DateTimeOriginal']=='2026:01:02 03:04:05'
    assert driver.dates.read(output)['ExifIFD:ExifImageWidth']==expected['width']


def test_real_small_jpeg_without_exif_is_not_enlarged(tmp_path):
    Image=pytest.importorskip('PIL.Image',reason='Falta Pillow real')
    source=tmp_path/'without-exif.jpg';output=tmp_path/'output.jpg'
    Image.new('RGB',(64,32),'green').save(source)
    assert not Image.open(source).getexif()
    expected=inspect_image(source,1200)
    render_image(source,output,parse_export_settings({}))
    assert validate_image(output,expected)['width']==64
