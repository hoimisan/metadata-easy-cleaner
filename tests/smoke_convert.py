from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image
from PIL.PngImagePlugin import PngInfo

from app import ConvertOptions, build_output_path, convert_image, read_image_metadata


def main() -> None:
    work = ROOT / "tmp_smoke"
    if work.exists():
        shutil.rmtree(work)
    src_dir = work / "src"
    out_dir = work / "out"
    src_dir.mkdir(parents=True)
    out_dir.mkdir(parents=True)

    source = src_dir / "sample.png"
    image = Image.new("RGBA", (64, 64), (40, 90, 160, 255))
    png_info = PngInfo()
    png_info.add_text("parameters", "prompt: test prompt, steps: 20")
    image.save(source, pnginfo=png_info)

    source_metadata = read_image_metadata(source)
    assert source_metadata["info.parameters"] == "prompt: test prompt, steps: 20"

    png_options = ConvertOptions(
        output_format="PNG",
        output_dir=out_dir,
        rename_pattern="{name}_{number}",
        jpeg_quality=95,
        png_compress_level=6,
        overwrite=True,
        enhance_enabled=False,
        sharpness=1.0,
        contrast=1.0,
        color=1.0,
    )
    png_output = build_output_path(source, 1, 1, png_options)
    convert_image(source, png_output, png_options)

    with Image.open(source) as original, Image.open(png_output) as converted:
        assert original.size == converted.size
        assert original.tobytes() == converted.tobytes()
        assert not converted.info
        assert not read_image_metadata(png_output)

    jpg_options = ConvertOptions(
        output_format="JPEG",
        output_dir=out_dir,
        rename_pattern="{name}_jpg",
        jpeg_quality=92,
        png_compress_level=6,
        overwrite=True,
        enhance_enabled=True,
        sharpness=1.1,
        contrast=1.05,
        color=1.0,
    )
    jpg_output = build_output_path(source, 1, 1, jpg_options)
    convert_image(source, jpg_output, jpg_options)

    with Image.open(jpg_output) as converted_jpg:
        assert converted_jpg.format == "JPEG"
        assert converted_jpg.mode == "RGB"

    shutil.rmtree(work)
    print("smoke_convert: ok")


if __name__ == "__main__":
    main()
