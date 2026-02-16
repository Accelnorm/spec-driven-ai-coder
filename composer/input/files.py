from typing import Dict
import os
import zlib
import anthropic

from composer.input.types import CommandLineArgs, InputData, UploadedFile, LocalFile

def upload_file_if_needed(client: anthropic.Anthropic, file_path: str, uploaded_files: Dict[str, str]) -> UploadedFile:
    """Upload a file if not already uploaded, return UploadedFile."""
    with open(file_path, 'rb') as f_bytes:
        crc_hex = hex(zlib.crc32(f_bytes.read()))
    basename = os.path.basename(file_path)
    crc_basename = f"{crc_hex}_{basename}"
    if crc_basename not in uploaded_files:
        print(f"Uploading {basename}... (canonical name {crc_basename})")
        uploaded_file = client.beta.files.upload(
            file=(crc_basename, open(file_path, "rb"), "text/plain")
        )
        print(f"Uploaded {basename} with ID: {uploaded_file.id}")
        return UploadedFile(file_id=uploaded_file.id, basename=basename, path=file_path)
    else:
        print(f"Found existing {basename} with ID: {uploaded_files[crc_basename]} (canonical name {crc_basename})")
        return UploadedFile(file_id=uploaded_files[crc_basename], basename=basename, path=file_path)

def upload_input(i: CommandLineArgs) -> InputData:
    """Upload input files to Anthropic API (or load locally for local LLMs)."""
    if i.provider != "anthropic":
        return load_input_local(i)
    
    client = anthropic.Anthropic()
    d: Dict[str, str] = {}
    for f in client.beta.files.list():
        d[f.filename] = f.id

    # Upload the three input files
    interface_file = upload_file_if_needed(client, i.interface_file, d)
    spec_file = upload_file_if_needed(client, i.spec_file, d)
    system_doc_file = upload_file_if_needed(client, i.system_doc, d)

    return InputData(
        spec=spec_file,
        system_doc=system_doc_file,
        intf=interface_file,
    )


def load_input_local(i: CommandLineArgs) -> InputData:
    """Load input files locally for use with local LLMs (no API upload)."""
    interface_file = LocalFile(
        basename=os.path.basename(i.interface_file),
        path=i.interface_file
    )
    spec_file = LocalFile(
        basename=os.path.basename(i.spec_file),
        path=i.spec_file
    )
    system_doc_file = LocalFile(
        basename=os.path.basename(i.system_doc),
        path=i.system_doc
    )

    return InputData(
        spec=spec_file,  # type: ignore[arg-type]
        system_doc=system_doc_file,  # type: ignore[arg-type]
        intf=interface_file,  # type: ignore[arg-type]
    )
