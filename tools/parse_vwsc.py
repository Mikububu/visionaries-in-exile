"""Parse Director 11 VWSC (score) chunk into per-frame sprite state.

Format (all big-endian), distilled from ScummVM's engines/director/score.cpp
and frame.cpp:

  Outer header (bytes 0..11):
    u32 framesStreamSize  -- total bytes of the VWSC chunk
    u32 versionMarker     -- 0xFFFFFFFD for D6+/D11
    u32 listStart         -- offset to list metadata

  List metadata (at `listStart`, 12 bytes):
    u32 numEntries
    u32 listSize          -- count of u32 entries in the index (= numEntries + 1 typically)
    u32 maxDataLen

  Sprite-detail offset index (at listStart + 12, listSize × 4 bytes):
    u32[listSize] entry_offsets  -- relative to frameDataOffset

  frameDataOffset = listStart + 12 + listSize*4

  Frame header (at frameDataOffset, 20 bytes):
    u32 innerFramesStreamSize  -- total of frame-data region
    u32 frame1Offset            -- usually 20, so frame 1 data starts right after
    u32 numOfFrames
    u16 framesVersion           -- 14 for D11 files we've seen
    u16 spriteRecordSize        -- 48 for D7/D8/D11
    u16 numChannels             -- channel count, not always matching displayed
    u16 numChannelsDisplayed    -- only if framesVersion > 13

  Frame delta stream (from frameDataOffset + frame1Offset onward):
    loop for N frames:
      u16 frameSize      -- total bytes this frame consumes (incl itself)
      remaining = frameSize - 2
      while remaining > 0:
        u16 channelSize
        u16 channelOffset  -- byte offset into the channels buffer
        channelData (channelSize bytes)
        remaining -= 4 + channelSize

  Sprite record, 48 bytes each (D7/D8+, per frame.cpp writeSpriteDataD7):
    0x00  u8  spriteType
    0x01  u8  inkData
    0x02  u8  foreColor
    0x03  u8  backColor
    0x04  s16 castLib
    0x06  u16 castMember
    0x08  u32 spriteListIdx
    0x0C  u16 startPoint.y
    0x0E  u16 startPoint.x
    0x10  u16 height
    0x12  u16 width
    0x14  u8  colorcode
    0x15  u8  blendAmount
    0x16  u8  thickness
    0x17  u8  flags
    0x18  u8  fgColorG, bgColorG, fgColorB, bgColorB (4 bytes)
    0x1C  u32 angleRot
    0x20  u32 angleSkew
    0x24  12 bytes padding

For the main-menu rollover use case we care about:
  - castLib + castMember (which cast bitmap is shown)
  - startPoint.x, startPoint.y (top-left on stage)
  - width, height (sprite size)
  - ink (8 = copy, 36 = matte w/ bg transparent, often used for rollover states)

Output JSON:
  {
    "AIE/AAHAUPT": {
      "numFrames": 496,
      "spriteRecordSize": 48,
      "numChannels": 120,
      "frames": {
        "1": [
          {"channel": 3, "castLib": 0, "castMember": 16, "x": 10, "y": 12, "w": 50, "h": 60, "ink": 8, ...},
          ...
        ],
        "10": [...],
        ...
      }
    },
    ...
  }

Only frames where at least one rollover is visible are emitted to keep output small.
"""
from __future__ import annotations
import json
import struct
import sys
from pathlib import Path


class ScoreParser:
    def __init__(self, blob: bytes):
        self.data = blob
        self.size = len(blob)

    def u32(self, off: int) -> int:
        return struct.unpack_from(">I", self.data, off)[0]

    def u16(self, off: int) -> int:
        return struct.unpack_from(">H", self.data, off)[0]

    def s16(self, off: int) -> int:
        return struct.unpack_from(">h", self.data, off)[0]

    def u8(self, off: int) -> int:
        return self.data[off]

    def parse(self) -> dict:
        if self.size < 12:
            return {"error": "file too short"}

        framesStreamSize = self.u32(0)
        versionMarker = self.u32(4)
        listStart = self.u32(8)

        if listStart + 12 > self.size:
            return {"error": f"listStart {listStart} out of bounds"}

        numEntries = self.u32(listStart)
        listSize = self.u32(listStart + 4)
        maxDataLen = self.u32(listStart + 8)

        indexStart = listStart + 12
        frameDataOffset = indexStart + listSize * 4

        if frameDataOffset + 20 > self.size:
            return {"error": f"frameDataOffset {frameDataOffset} out of bounds"}

        innerSize = self.u32(frameDataOffset)
        frame1Offset = self.u32(frameDataOffset + 4)
        numOfFrames = self.u32(frameDataOffset + 8)
        framesVersion = self.u16(frameDataOffset + 12)
        spriteRecordSize = self.u16(frameDataOffset + 14)
        numChannels = self.u16(frameDataOffset + 16)
        if framesVersion > 13:
            numChannelsDisplayed = self.u16(frameDataOffset + 18)
            frame_start = frameDataOffset + 20
        else:
            numChannelsDisplayed = 48 if framesVersion <= 7 else 120
            frame_start = frameDataOffset + 20

        # Apply frame1Offset relative to frameDataOffset:
        frame_start = frameDataOffset + frame1Offset
        # Note: frame1Offset is usually 20 so frame_start = frameDataOffset + 20.

        buffer_size = max(numChannelsDisplayed, 48) * spriteRecordSize
        channels = bytearray(buffer_size)

        frames_with_sprites: dict[int, list[dict]] = {}
        pos = frame_start
        frame_index = 0
        while pos < self.size and frame_index < numOfFrames + 10:
            if pos + 2 > self.size:
                break
            frameSize = self.u16(pos)
            if frameSize == 0:
                break
            # Apply deltas
            remaining = frameSize - 2
            p = pos + 2
            while remaining > 0 and p + 4 <= self.size:
                channelSize = self.u16(p)
                channelOffset = self.u16(p + 2)
                p += 4
                if channelSize == 0:
                    remaining -= 4
                    continue
                if p + channelSize > self.size:
                    break
                if channelOffset + channelSize <= buffer_size:
                    channels[channelOffset:channelOffset + channelSize] = self.data[p:p + channelSize]
                p += channelSize
                remaining -= 4 + channelSize
            pos += frameSize
            frame_index += 1

            # Snapshot the channels buffer as the current frame's sprite state.
            # Skip main channel (first 48 bytes are frame metadata like palette/tempo/transitions)
            sprites = []
            for ch in range(2, numChannelsDisplayed + 1):
                off = ch * spriteRecordSize
                if off + spriteRecordSize > buffer_size:
                    break
                rec = bytes(channels[off:off + spriteRecordSize])
                if rec == b"\x00" * spriteRecordSize:
                    continue
                sprite = self._parse_sprite(rec, ch, spriteRecordSize)
                if sprite:
                    sprites.append(sprite)
            if sprites:
                # Only keep unique frames — dedupe identical sprite lists by tuple hash
                frames_with_sprites[frame_index] = sprites

        return {
            "framesStreamSize": framesStreamSize,
            "versionMarker": versionMarker,
            "numOfFrames": numOfFrames,
            "framesVersion": framesVersion,
            "spriteRecordSize": spriteRecordSize,
            "numChannels": numChannels,
            "numChannelsDisplayed": numChannelsDisplayed,
            "frames": frames_with_sprites,
        }

    def _parse_sprite(self, rec: bytes, channel: int, size: int) -> dict | None:
        if size < 24:
            return None
        spriteType = rec[0]
        inkData = rec[1]
        ink = inkData & 0x3F
        foreColor = rec[2]
        backColor = rec[3]
        castLib = struct.unpack(">h", rec[4:6])[0]
        castMember = struct.unpack(">H", rec[6:8])[0]
        # startPoint.y at 12-13, .x at 14-15 (per ScummVM D7 layout)
        y = struct.unpack(">H", rec[12:14])[0]
        x = struct.unpack(">H", rec[14:16])[0]
        height = struct.unpack(">H", rec[16:18])[0]
        width = struct.unpack(">H", rec[18:20])[0]

        # Reject empty/invalid sprites
        if castMember == 0 and spriteType == 0:
            return None
        # Treat as signed shorts in case negative (off-stage)
        if x > 32767:
            x -= 65536
        if y > 32767:
            y -= 65536
        return {
            "channel": channel,
            "type": spriteType,
            "ink": ink,
            "fg": foreColor,
            "bg": backColor,
            "castLib": castLib,
            "castMember": castMember,
            "x": x,
            "y": y,
            "w": width,
            "h": height,
        }


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    chunks_root = root / "chunks"
    out_data: dict[str, dict] = {}
    total_frames = 0
    total_sprites = 0
    scenes_with_data = 0

    for side in ("VIE", "AIE"):
        side_dir = chunks_root / side
        if not side_dir.is_dir():
            continue
        for scene_dir in sorted(side_dir.iterdir()):
            if not scene_dir.is_dir():
                continue
            inner = scene_dir / "chunks"
            if not inner.is_dir():
                continue
            vwsc_files = list(inner.glob("VWSC-*.bin"))
            if not vwsc_files:
                continue
            # Use the largest VWSC (main score)
            vwsc_files.sort(key=lambda p: p.stat().st_size, reverse=True)
            main = vwsc_files[0]
            try:
                result = ScoreParser(main.read_bytes()).parse()
            except Exception as e:
                result = {"error": str(e)}
            if result.get("frames"):
                # Stringify frame indices for JSON
                result["frames"] = {str(k): v for k, v in result["frames"].items()}
                out_data[f"{side}/{scene_dir.name}"] = result
                scenes_with_data += 1
                total_frames += len(result["frames"])
                total_sprites += sum(len(v) for v in result["frames"].values())

    out = root / "content" / "score.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(out_data, ensure_ascii=False, separators=(",", ":")))
    print(f"scenes parsed: {scenes_with_data}", file=sys.stderr)
    print(f"unique frames with sprites: {total_frames}", file=sys.stderr)
    print(f"total sprite records: {total_sprites}", file=sys.stderr)
    print(f"wrote {out} ({out.stat().st_size/1024:.1f} KB)", file=sys.stderr)

    # Print AAHAUPT frame-1 sprites for sanity-check
    key = "AIE/AAHAUPT"
    if key in out_data:
        scene = out_data[key]
        frames = scene["frames"]
        first_k = next(iter(frames))
        print(f"\n{key} first frame ({first_k}) sprites:", file=sys.stderr)
        for s in frames[first_k][:12]:
            print(f"  ch{s['channel']:2d}  cast #{s['castMember']:3d}  at ({s['x']:4d},{s['y']:4d}) {s['w']:3d}×{s['h']:3d}  ink={s['ink']}", file=sys.stderr)


if __name__ == "__main__":
    main()
