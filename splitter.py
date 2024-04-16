import argparse
import json
import os
import time
from collections import defaultdict
from copy import copy
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List


# https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#reference-buffer
@dataclass(kw_only=True)
class Buffer:
    byteLength: int
    # Optional
    uri: str = None
    name: str = None
    extensions: str = None
    extras: str = None


# https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#_gltf_buffers
@dataclass
class Buffers:
    KEY = "buffers"

    buffers: List[Buffer]


# https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#reference-bufferview
@dataclass(kw_only=True)
class BufferView:
    buffer: int
    byteLength: int
    # Optional
    byteOffset: int = None
    byteStride: int = None
    target: int = None
    name: str = None
    extensions: str = None
    extras: str = None


# https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#_gltf_bufferviews
@dataclass
class BufferViews:
    KEY = "bufferViews"

    bufferViews: List[BufferView]


def main():
    ctx = parse_arguments()

    # change working dir to provided one
    path = Path(ctx.path)
    os.chdir(path.parent)

    with open(path.name, "r+") as file:  # edit mode
        if ctx.verbose:
            print("Parsing {model}...".format(model=path.name))

        data = json.load(file)

        # deserialize gltf model data
        buffers = Buffers([Buffer(**b) for b in data[Buffers.KEY]])
        buffer_views = BufferViews([BufferView(**bv) for bv in data[BufferViews.KEY]])

        # build BufferViews lookup map
        views = defaultdict(list)
        for view in buffer_views.bufferViews:
            views[view.buffer].append(view)

        # process buffers
        out_buffers = Buffers([])
        for (buffer_idx, buffer) in enumerate(buffers.buffers):
            if ctx.verbose:
                print("\nProcessing buffer [{buffer}]".format(buffer=buffer))
            chunks = collect_chunks(buffer, views[buffer_idx], len(out_buffers.buffers), ctx.limit, ctx.verbose)
            out_buffers.buffers.extend(chunks)
            save_chunks(chunks, buffer, ctx.verbose)

        # helper to clear default (None) values
        def todict(dclass):
            return asdict(dclass, dict_factory=lambda d: dict({k: v for (k, v) in d if v is not None}))

        # serialize updated gltf model data
        data.update(todict(out_buffers))
        data.update(todict(buffer_views))

        # clear given json before writing
        file.seek(0)
        file.truncate()

        # finally save updated gltf
        if ctx.verbose:
            print("\nSaving {model}...".format(model=path.name))
        indent = "  " if ctx.format else None
        json.dump(data, file, indent=indent)


def parse_arguments():
    parser = argparse.ArgumentParser(
        prog="glTF-splitter",
        description="Splits asset's buffers into chunks according to provided maximum size. "
                    "Does not rearrange existing buffers, but only splits ones over the limit. "
                    "CARE: the script modifies given resources.",
    )

    parser.add_argument(
        "-p", "--path",
        type=str, required=True,
        help="Path to glTF asset.",
    )

    parser.add_argument(
        "-l", "--limit",
        type=int, default=0,
        help="Size limit for included binary buffers (.bin, .glbin, or .glbuf). "
             "0 to split by each view. "
             "Note: size should be grater or equal than the largest view. "
             "Default=0."
    )

    parser.add_argument(
        "-f", "--format",
        action='store_true',
        help="Pretty print resulting gltf.",
    )

    parser.add_argument(
        "-v", "--verbose",
        action='store_true',
        help="Detailed logging.",
    )

    return parser.parse_args()


def collect_chunks(buffer, views, buffer_idx, size_limit, verbose=False):
    if verbose:
        print("Collecting chunks...")

    # embedded buffers are not supported
    if buffer.uri is None:
        print("Failed to split buffer [{buffer}]. Missing uri.".format(buffer=buffer))
        raise RuntimeError("Missing buffer's uri")  # Embedded buffers are not supported

    chunks = []

    # not trying to find the most efficient (memory) packing layout
    for view in sorted(views, key=lambda v: v.byteOffset or 0):
        if 0 < size_limit < view.byteLength:
            print("Failed to split buffer [{buffer}]. Size limit ({limit}) is less than view's size ({size}).".format(
                buffer=buffer, limit=size_limit, size=view.byteLength))
            raise RuntimeError("Wrong limit")

        # add a new chunk. use base one as prototype
        if len(chunks) == 0 or size_limit == 0 or chunks[-1].byteLength + view.byteLength > size_limit:
            chunks.append(copy(buffer))
            chunks[-1].byteLength = 0
            if verbose:
                print("Adding new chunk [{chunk}]".format(chunk=chunks[-1]))

        # append view to the tail chunk
        chunk = chunks[-1]
        view.buffer = buffer_idx + len(chunks) - 1
        view.byteOffset = chunk.byteLength
        chunk.byteLength += view.byteLength
        if verbose:
            print("Adding view [{view}] to chunk".format(view=view))

    if verbose:
        print("{} chunks collected.".format(len(chunks)))

    return chunks


def save_chunks(chunks, buffer, verbose=False):
    if verbose:
        print("Saving chunks...")

    if len(chunks) == 1:  # nothing to actually split
        if verbose:
            print("Buffer fits the limit. Nothing to save.")
        return

    with open(buffer.uri, "rb") as buffer_data:
        for (chunk_idx, chunk) in enumerate(chunks):
            # rename chunks
            postfix = "_{}".format(chunk_idx)
            uri = Path(chunk.uri)
            chunk.uri = str(uri.with_stem(uri.stem + postfix))
            if chunk.name is not None:
                chunk.name += postfix

            with open(chunk.uri, "wb+") as chunk_data:  # CARE: name collisions could occur
                if verbose:
                    print("Saving chunk [{chunk}]".format(chunk=chunk))
                # bufferized copying
                to_read = chunk.byteLength
                while to_read:
                    to_read -= chunk_data.write(buffer_data.read(min(to_read, 1024)))

    # remove base buffer
    os.remove(buffer.uri)


if __name__ == "__main__":
    start_time = time.time()

    main()

    print("Total time: {:.5f} seconds".format(time.time() - start_time))
