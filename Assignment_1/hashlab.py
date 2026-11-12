
import argparse
import base64
import hashlib
import json
import sys
import unicodedata
from pathlib import Path


# --------------------------------------------------
# Core SHA-256 functionality
# --------------------------------------------------

def calculate_sha256(data):
    """Calculate SHA-256 for bytes."""
    digest = hashlib.sha256(data).digest()
    return digest


def display_hash(digest, byte_length):
    """Display hash diagnostics."""
    print(f"bytes: {byte_length}")
    print(f"sha256: {digest.hex()}")
    print(f"base64: {base64.b64encode(digest).decode('ascii')}")


def hash_bytes(data):
    """Hash an in-memory byte sequence."""
    digest = calculate_sha256(data)
    display_hash(digest, len(data))


# --------------------------------------------------
# Text mode
# --------------------------------------------------

def text_mode(text):
    """Hash UTF-8 encoded text."""
    data = text.encode("utf-8")
    hash_bytes(data)


# --------------------------------------------------
# Hex mode
# --------------------------------------------------

def hex_mode(hex_string):
    """Convert hexadecimal string to bytes and hash it."""
    try:
        data = bytes.fromhex(hex_string)
    except ValueError:
        print("Error: Invalid hexadecimal input.", file=sys.stderr)
        sys.exit(1)

    hash_bytes(data)


# --------------------------------------------------
# File mode (streaming)
# --------------------------------------------------

def file_mode(filename):
    """
    Hash a file in chunks.
    Does not load the entire file into memory.
    """
    sha256 = hashlib.sha256()
    total_bytes = 0

    try:
        with open(filename, "rb") as file:
            while True:
                chunk = file.read(1024 * 1024)  # 1 MB chunks

                if not chunk:
                    break

                sha256.update(chunk)
                total_bytes += len(chunk)

    except OSError as error:
        print(f"Error reading file: {error}", file=sys.stderr)
        sys.exit(1)

    display_hash(sha256.digest(), total_bytes)


# --------------------------------------------------
# Avalanche effect
# --------------------------------------------------

def avalanche_mode(data, bit_position):
    """
    Flip one selected bit and calculate
    the Hamming distance between SHA-256 digests.

    Bit positions are zero-indexed, starting
    from the least significant bit of byte 0.
    """
    if not data:
        print("Error: Cannot flip a bit in empty input.")
        sys.exit(1)

    total_bits = len(data) * 8

    if bit_position < 0 or bit_position >= total_bits:
        print(
            f"Error: Bit position must be between 0 and "
            f"{total_bits - 1}."
        )
        sys.exit(1)

    original = bytearray(data)
    modified = bytearray(data)

    byte_index = bit_position // 8
    bit_index = bit_position % 8

    # Flip exactly one bit
    modified[byte_index] ^= (1 << bit_index)

    original_hash = calculate_sha256(bytes(original))
    modified_hash = calculate_sha256(bytes(modified))

    # XOR the digests and count differing bits
    difference = int.from_bytes(original_hash, "big") ^ int.from_bytes(
        modified_hash, "big"
    )

    hamming_distance = difference.bit_count()

    print(f"original_sha256: {original_hash.hex()}")
    print(f"modified_sha256: {modified_hash.hex()}")
    print(f"changed_bits_in_digest: {hamming_distance}")
    print(f"total_digest_bits: 256")
    print(
        f"percentage_changed: "
        f"{(hamming_distance / 256) * 100:.2f}%"
    )


def avalanche_command(args):
    if args.text is not None:
        data = args.text.encode("utf-8")

    elif args.hex is not None:
        try:
            data = bytes.fromhex(args.hex)
        except ValueError:
            print("Error: Invalid hexadecimal input.", file=sys.stderr)
            sys.exit(1)

    elif args.file is not None:
        try:
            with open(args.file, "rb") as file:
                data = file.read()
        except OSError as error:
            print(f"Error reading file: {error}", file=sys.stderr)
            sys.exit(1)

    else:
        print("Error: Provide --text, --hex, or --file.")
        sys.exit(1)

    avalanche_mode(data, args.bit)


# --------------------------------------------------
# Canonical JSON
# --------------------------------------------------

def canonicalize_json(data):
    """
    Deterministic JSON serialization rules:

    1. Sort dictionary keys alphabetically.
    2. Remove unnecessary whitespace.
    3. Preserve Unicode characters.
    4. Use UTF-8 encoding.
    5. Reject NaN and Infinity.
    6. Preserve JSON value types.
    """
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False
    ).encode("utf-8")


def canonical_json_mode(filename):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError("Input JSON must be an object.")

        canonical_bytes = canonicalize_json(data)

        print("canonical_json:")
        print(canonical_bytes.decode("utf-8"))

        hash_bytes(canonical_bytes)

    except (OSError, json.JSONDecodeError, ValueError,
            UnicodeDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)


# --------------------------------------------------
# Byte-level difference demonstrations
# --------------------------------------------------

def demonstrations():
    print("\n========== HASHLAB DEMONSTRATIONS ==========\n")

    # 1. Newline differences
    print("1. Newline Difference")

    a = b"Alice pays Bob 10"
    b = b"Alice pays Bob 10\n"

    print("Without newline:")
    hash_bytes(a)

    print("\nWith trailing newline:")
    hash_bytes(b)

    print("\nAre hashes equal?", calculate_sha256(a) ==
          calculate_sha256(b))

    # 2. Unicode normalization
    print("\n2. Unicode Normalization")

    composed = "\u00e9"          # é
    decomposed = "e\u0301"       # e + combining accent

    print("Composed UTF-8:", composed.encode("utf-8").hex())
    print("Decomposed UTF-8:", decomposed.encode("utf-8").hex())

    hash_bytes(composed.encode("utf-8"))
    hash_bytes(decomposed.encode("utf-8"))

    normalized = unicodedata.normalize("NFC", decomposed)

    print("After NFC normalization:")
    print("Hashes equal:", calculate_sha256(
        composed.encode("utf-8")
    ) == calculate_sha256(normalized.encode("utf-8")))

    # 3. Integer versus string
    print("\n3. Integer versus String")

    integer_value = json.dumps({"amount": 10}).encode("utf-8")
    string_value = json.dumps({"amount": "10"}).encode("utf-8")

    print("Integer JSON:")
    hash_bytes(integer_value)

    print("\nString JSON:")
    hash_bytes(string_value)

    # 4. Key ordering
    print("\n4. JSON Key Ordering")

    json_a = {"name": "Alice", "amount": 10}
    json_b = {"amount": 10, "name": "Alice"}

    bytes_a = canonicalize_json(json_a)
    bytes_b = canonicalize_json(json_b)

    print("Canonical JSON A:", bytes_a.decode("utf-8"))
    print("Canonical JSON B:", bytes_b.decode("utf-8"))

    print("Hashes equal:", calculate_sha256(bytes_a) ==
          calculate_sha256(bytes_b))

    print("\n========== END OF DEMONSTRATIONS ==========")


# --------------------------------------------------
# Argument parser / CLI
# --------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="hashlab",
        description="SHA-256 diagnostics command-line tool"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True
    )

    # Text command
    text_parser = subparsers.add_parser(
        "text",
        help="Hash UTF-8 text"
    )
    text_parser.add_argument("text")

    # Hex command
    hex_parser = subparsers.add_parser(
        "hex",
        help="Hash hexadecimal bytes"
    )
    hex_parser.add_argument("hex_string")

    # File command
    file_parser = subparsers.add_parser(
        "file",
        help="Hash a file using streaming"
    )
    file_parser.add_argument("filename")

    # Avalanche command
    avalanche_parser = subparsers.add_parser(
        "avalanche",
        help="Demonstrate the avalanche effect"
    )

    input_group = avalanche_parser.add_mutually_exclusive_group(
        required=True
    )

    input_group.add_argument("--text")
    input_group.add_argument("--hex")
    input_group.add_argument("--file")

    avalanche_parser.add_argument(
        "--bit",
        type=int,
        required=True,
        help="Zero-indexed bit position to flip"
    )

    # Canonical JSON command
    json_parser = subparsers.add_parser(
        "canonical-json",
        help="Canonicalize and hash a JSON object"
    )
    json_parser.add_argument("filename")

    # Demonstration command
    subparsers.add_parser(
        "demo",
        help="Demonstrate byte-level differences"
    )

    args = parser.parse_args()

    if args.command == "text":
        text_mode(args.text)

    elif args.command == "hex":
        hex_mode(args.hex_string)

    elif args.command == "file":
        file_mode(args.filename)

    elif args.command == "avalanche":
        avalanche_command(args)

    elif args.command == "canonical-json":
        canonical_json_mode(args.filename)

    elif args.command == "demo":
        demonstrations()


if __name__ == "__main__":
    main()
