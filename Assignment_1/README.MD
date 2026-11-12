
# Hashlab – SHA-256 Diagnostics Tool

## Overview

Hashlab is a command-line tool developed in Python to demonstrate SHA-256 hashing and its security properties relevant to blockchain technology.

The tool accepts text, hexadecimal byte strings, and files as input and generates SHA-256 hash diagnostics. It also demonstrates the avalanche effect, deterministic JSON serialization, and how small differences in input bytes produce different hash outputs.

The SHA-256 algorithm is not implemented from scratch. Instead, Hashlab uses Python's trusted standard-library `hashlib` implementation.

## Features

- **Text Hashing:** Accepts text input, encodes it using UTF-8, and calculates its SHA-256 hash.
- **Hexadecimal Hashing:** Converts hexadecimal strings into bytes and calculates their SHA-256 hash.
- **File Hashing:** Processes files in chunks to support large files without loading the entire file into memory.
- **Hash Diagnostics:** Displays:
  - Input byte length
  - SHA-256 digest in hexadecimal format
  - SHA-256 digest in Base64 format
- **Avalanche Effect:** Flips a selected input bit and calculates the Hamming distance between the original and modified SHA-256 digests.
- **Canonical JSON:** Serializes JSON objects deterministically and hashes their UTF-8 representation.
- **Byte-Level Demonstrations:** Demonstrates how newline differences, Unicode normalization, integer versus string values, and JSON key ordering affect hashing.

## Project Structure

```text
hashlab/
│
├── hashlab.py
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.8 or later
- No external Python packages are required.

The project uses the following Python standard-library modules:

- `hashlib` – SHA-256 hashing
- `base64` – Base64 encoding of digests
- `argparse` – Command-line argument parsing
- `json` – JSON parsing and serialization
- `sys` – Error handling
- `unicodedata` – Unicode normalization demonstrations

## Installation

### 1. Clone or download the project

Navigate to the project directory:

```bash
cd hashlab
```

### 2. Verify Python installation

```bash
python --version
```

### 3. Install requirements

```bash
pip install -r requirements.txt
```

Since the project uses only standard-library modules, no additional packages need to be installed.

## Usage

Run the tool using the following syntax:

```bash
python hashlab.py <command> [arguments]
```

### 1. Text Mode

Calculates the SHA-256 hash of UTF-8 encoded text.

**Command:**

```bash
python hashlab.py text "Alice pays Bob 10"
```

**Output:**

```text
bytes: 18
sha256: <64-character hexadecimal digest>
base64: <Base64 encoded digest>
```

### 2. Hex Mode

Accepts a hexadecimal string, converts it into bytes, and calculates its SHA-256 hash.

**Command:**

```bash
python hashlab.py hex 416c696365
```

The hexadecimal input represents the bytes corresponding to the text `Alice`.

Malformed hexadecimal input is rejected with an error message.

### 3. File Mode

Calculates the SHA-256 hash of a file using streaming.

**Command:**

```bash
python hashlab.py file sample.txt
```

The file is read in chunks of 1 MB. This avoids loading the entire file into memory and makes the implementation suitable for large files.

### 4. Avalanche Command

Demonstrates the avalanche effect by flipping one selected bit in the input.

**Command:**

```bash
python hashlab.py avalanche --text "Alice pays Bob 10" --bit 7
```

**Output:**

```text
original_sha256: <original digest>
modified_sha256: <modified digest>
changed_bits_in_digest: <Hamming distance>
total_digest_bits: 256
percentage_changed: <percentage>
```

The bit position is zero-indexed, starting from the least significant bit of the first byte.

The command also supports hexadecimal and file inputs:

```bash
python hashlab.py avalanche --hex 416c696365 --bit 3
```

```bash
python hashlab.py avalanche --file sample.txt --bit 7
```

### 5. Canonical JSON

Reads a JSON object, serializes it deterministically, and calculates its SHA-256 hash.

Create a file named `sample.json`:

```json
{
    "name": "Alice",
    "amount": 10,
    "receiver": "Bob"
}
```

**Command:**

```bash
python hashlab.py canonical-json sample.json
```

**Canonicalization Rules:**

1. JSON object keys are sorted alphabetically.
2. Unnecessary whitespace is removed.
3. Unicode characters are preserved without ASCII escaping.
4. The serialized JSON is encoded using UTF-8.
5. NaN and Infinity values are rejected.
6. JSON value types are preserved.

These rules ensure that equivalent JSON objects with different key orders produce identical canonical representations and hashes.

### 6. Demonstration Mode

Runs demonstrations showing how different byte representations affect SHA-256 hashes.

**Command:**

```bash
python hashlab.py demo
```

The demonstrations cover:

- **Newline Differences:** Compares text with and without a trailing newline.
- **Unicode Normalization:** Compares composed and decomposed Unicode representations.
- **Integer vs String:** Compares JSON integer `10` with JSON string `"10"`.
- **JSON Key Ordering:** Demonstrates how canonical serialization produces identical hashes for objects with different key orders.

## Technical Implementation

### SHA-256 Hashing

The project uses Python's built-in `hashlib.sha256()` function to calculate SHA-256 digests.

The resulting 256-bit digest is represented in two formats:

- Hexadecimal: 64 hexadecimal characters.
- Base64: Encoded representation of the 32-byte digest.

### Streaming File Processing

Files are opened in binary mode (`rb`) and processed in chunks of 1 MB.

The hash object is updated incrementally using:

```python
sha256.update(chunk)
```

This approach ensures that memory consumption remains approximately constant regardless of file size.

### Avalanche Effect

The avalanche effect is an important cryptographic hash property. A small change in the input should produce a significantly different output.

Hashlab flips one selected input bit and compares the two resulting 256-bit digests using XOR.

The Hamming distance is calculated by counting the number of set bits in the XOR result.

For a secure hash function, changing one input bit is expected to change approximately half of the output bits (around 128 out of 256).

## Testing and Verification

The SHA-256 output can be independently verified using trusted system utilities.

**Windows:**

```powershell
certutil -hashfile sample.txt SHA256
```

**Linux:**

```bash
sha256sum sample.txt
```

**macOS:**

```bash
shasum -a 256 sample.txt
```

The hexadecimal digest produced by Hashlab should match the output of the corresponding independent utility.

### Large File Test

To test streaming functionality, create a 100 MB test file:

```python
with open("large_test.bin", "wb") as f:
    for _ in range(100):
        f.write(b"A" * 1024 * 1024)
```

Run:

```bash
python hashlab.py file large_test.bin
```

Verify that the resulting digest matches the independent SHA-256 utility.

## Relevance to Blockchain Security

Hashlab demonstrates several properties that are important in blockchain systems:

1. **Deterministic Hashing:** The same byte sequence always produces the same SHA-256 digest.
2. **Avalanche Effect:** A small input modification produces a substantially different digest.
3. **Data Integrity:** Hashes can be used to detect modifications to files and transaction data.
4. **Canonical Serialization:** Deterministic JSON serialization helps ensure that equivalent structured data produces consistent hashes.
5. **Efficient Processing:** Streaming allows large files and data objects to be hashed without requiring the entire input to reside in memory.

SHA-256 is widely used in blockchain systems for data integrity, transaction identifiers, and cryptographic linking of blocks.

## Limitations

- SHA-256 is a cryptographic hash function, not an encryption algorithm.
- Hashes cannot be reversed to recover the original input.
- Canonical JSON follows the serialization rules documented in this project and is not a complete implementation of the RFC 8785 JSON Canonicalization Scheme.
- The avalanche effect is demonstrated experimentally and does not constitute a formal security proof.
- The current avalanche implementation uses in-memory byte arrays, unlike the streaming file-hashing implementation.

