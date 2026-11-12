"""Minimal binary AndroidManifest.xml (AXML) reader / patcher.

Only what this rebuild needs: locate <uses-sdk android:targetSdkVersion="..."/>
and rewrite the compiled integer value in place. No resource table is touched,
so every resource ID in the app stays exactly where it was.
"""

import struct

RES_STRING_POOL = 0x0001
RES_XML_RESOURCE_MAP = 0x0180
RES_XML_START_ELEMENT = 0x0102

ATTR_TARGET_SDK = 0x01010270
TYPE_INT_DEC = 0x10
NO_ENTRY = 0xFFFFFFFF


class AxmlError(Exception):
    pass


def _decode_utf8(data, off):
    n = struct.unpack_from('<H', data, off)[0]
    off += 2
    if n & 0x8000:
        n = ((n & 0x7FFF) << 16) | struct.unpack_from('<H', data, off)[0]
        off += 2
    blen = data[off]
    off += 1
    return data[off:off + blen].decode('utf-8', 'replace'), off + blen + 1


def _decode_utf16(data, off):
    n = struct.unpack_from('<H', data, off)[0]
    off += 2
    if n & 0x8000:
        n = ((n & 0x7FFF) << 16) | struct.unpack_from('<H', data, off)[0]
        off += 2
    return data[off:off + n * 2].decode('utf-16-le', 'replace'), off + n * 2 + 2


def read_string_pool(data, off):
    _type, hsize, _size = struct.unpack_from('<HHI', data, off)
    count, _style_count, flags, strings_start, _styles_start = struct.unpack_from('<IIIII', data, off + 8)
    utf8 = bool(flags & 0x100)
    offsets = struct.unpack_from('<%dI' % count, data, off + hsize)
    base = off + strings_start
    out = []
    for so in offsets:
        if utf8:
            s, _ = _decode_utf8(data, base + so)
        else:
            s, _ = _decode_utf16(data, base + so)
        out.append(s)
    return out


def _chunks(data):
    off = 8
    while off + 8 <= len(data):
        ctype, hsize, size = struct.unpack_from('<HHI', data, off)
        if size < 8 or off + size > len(data):
            raise AxmlError('corrupt chunk at 0x%x' % off)
        yield off, ctype, hsize, size
        off += size


def patch_target_sdk(data, new_value):
    """Return (patched_bytes, old_value). Fails loudly if the edit is ambiguous."""
    data = bytearray(data)
    strings = None
    for off, ctype, hsize, size in _chunks(data):
        if ctype == RES_STRING_POOL:
            strings = read_string_pool(data, off)
        elif ctype == RES_XML_START_ELEMENT:
            name = strings[struct.unpack_from('<I', data, off + 20)[0]]
            if name != 'uses-sdk':
                continue
            attr_start, attr_size, attr_count = struct.unpack_from('<HHH', data, off + 24)
            base = off + 16 + attr_start  # offset is relative to ResXMLTree_attrExt
            for i in range(attr_count):
                a = base + i * attr_size
                aname = strings[struct.unpack_from('<I', data, a + 4)[0]]
                if aname != 'targetSdkVersion':
                    continue
                _sz, _res0, dtype, old = struct.unpack_from('<HBBI', data, a + 12)
                if dtype != TYPE_INT_DEC:
                    raise AxmlError('targetSdkVersion is not an int literal (type 0x%02x)' % dtype)
                struct.pack_into('<I', data, a + 8, NO_ENTRY)  # drop raw string
                struct.pack_into('<I', data, a + 16, new_value)
                return bytes(data), old
    raise AxmlError('uses-sdk/targetSdkVersion not found')
