"""JPEG RGB/L con orientación aplicada, ICC intacto y dimensiones EXIF coherentes."""

import hashlib


class ImagePolicyError(ValueError):
    pass


def modules():
    try:
        import PIL
        from PIL import Image, ImageOps, features
    except ImportError as exc:
        raise ImagePolicyError("Falta Pillow: instalar el extra images") from exc
    return PIL, Image, ImageOps, features


def inspect_image(path, limit):
    PIL, Image, ImageOps, features = modules()
    with Image.open(path) as image:
        if image.format != "JPEG" or image.mode not in ("RGB", "L") or getattr(image, "n_frames", 1) != 1:
            raise ImagePolicyError("Solo JPEG RGB/L de una imagen; conversión de modo/color pendiente de política")
        image.load()
        visual = ImageOps.exif_transpose(image)
        original = visual.size
        visual.thumbnail((limit, limit), Image.Resampling.LANCZOS)
        icc = image.info.get("icc_profile", b"")
        return {"width": visual.width, "height": visual.height, "visual_source": list(original), "mode": visual.mode,
                "icc_sha256": hashlib.sha256(icc).hexdigest(), "has_icc": bool(icc),
                "versions": {"Pillow": PIL.__version__, "JPEG": features.version_codec("jpg")}, "renderer": "jpeg-transpose-lanczos:v1"}


def render_image(source, destination, settings):
    _, Image, ImageOps, _ = modules()
    inspect_image(source, settings["image_max_side"])
    with Image.open(source) as image:
        image.load()
        output = ImageOps.exif_transpose(image)
        output.thumbnail((settings["image_max_side"], settings["image_max_side"]), Image.Resampling.LANCZOS)
        exif = output.getexif()
        exif[274], exif[256], exif[257] = 1, output.width, output.height
        exif_ifd = dict(exif.get_ifd(34665)) if 34665 in exif else {}
        exif_ifd.update({40962: output.width, 40963: output.height})
        exif[34665] = exif_ifd
        output.save(destination, format="JPEG", quality=settings["image_quality"], subsampling=0,
                    exif=exif, icc_profile=image.info.get("icc_profile"))


def validate_image(path, expected):
    _, Image, _, _ = modules()
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        image.load()
        exif = image.getexif()
        if image.format != "JPEG" or image.mode != expected["mode"] or image.size != (expected["width"], expected["height"]):
            raise ImagePolicyError("Formato/modo/geometría de JPG no coincide con la receta")
        dimensions = exif.get_ifd(34665)
        if exif.get(274) != 1 or dimensions.get(40962) != image.width or dimensions.get(40963) != image.height:
            raise ImagePolicyError("Orientation/dimensiones EXIF no normalizadas")
        if hashlib.sha256(image.info.get("icc_profile", b"")).hexdigest() != expected["icc_sha256"]:
            raise ImagePolicyError("Perfil ICC alterado o perdido")
        return {"decode": "complete", "width": image.width, "height": image.height, "orientation": 1,
                "mode": image.mode, "icc_sha256": expected["icc_sha256"]}
