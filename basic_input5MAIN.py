import hashlib
import csv
import os
import base64
import time
from bidict import bidict
from tqdm import tqdm

# --- CONFIGURATION ---
STORE_DIR = "registry_store"
TIMING_FILE = "curation_times.csv"


def ensure_directory():
    if not os.path.exists(STORE_DIR):
        os.makedirs(STORE_DIR)


def load_registry():
    """Loads existing CSV registries into a bidict for subsequent instantiations."""
    ensure_directory()
    registry_map = bidict()
    files = [f for f in os.listdir(STORE_DIR) if f.startswith("registry_k") and f.endswith(".csv")]

    if files:
        print("[*] Loading previously curated dictionary...")
        for file in tqdm(files, desc="Loading Registry CSVs"):
            filepath = os.path.join(STORE_DIR, file)
            with open(filepath, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # bidict key: binary_sequence. Value: (file_name, row_index, hash)
                    bin_seq = row['Binary_Sequence']
                    # Ensure unique values for bidict by using the tuple of location and hash
                    registry_map[bin_seq] = (file, int(row['Row_Index']), row['SHA256_Hash'])
    return registry_map


def get_next_row_index(filepath):
    if not os.path.exists(filepath):
        return 1
    with open(filepath, 'r') as f:
        return sum(1 for _ in f)


def log_curation_time(duration, new_items_count):
    file_exists = os.path.exists(TIMING_FILE)
    with open(TIMING_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Duration_Seconds", "New_Sequences_Added"])
        writer.writerow([time.strftime('%Y-%m-%d %H:%M:%S'), f"{duration:.4f}", new_items_count])


def file_to_binary_string(filepath):
    """Converts a file to base64, then translates that into a continuous binary string."""
    with open(filepath, "rb") as f:
        b64_data = base64.b64encode(f.read()).decode('utf-8')

    bin_str_list = []
    for char in tqdm(b64_data, desc="[*] Converting file to binary sequence..."):
        bin_str_list.append(format(ord(char), '08b'))
    return ''.join(bin_str_list)


def binary_string_to_file(bin_sequence, output_filepath):
    """Converts a continuous binary string back to base64, then writes the decoded file."""
    print("[*] Reconstituting original file data...")
    # Chop the continuous binary string into 8-bit blocks
    b64_chars = []
    for i in tqdm(range(0, len(bin_sequence), 8), desc="[*] Converting binary back to base64"):
        byte_chunk = bin_sequence[i:i + 8]
        if len(byte_chunk) == 8:
            b64_chars.append(chr(int(byte_chunk, 2)))

    b64_string = ''.join(b64_chars)
    # Decode Base64 back to original raw bytes
    file_bytes = base64.b64decode(b64_string.encode('utf-8'))

    with open(output_filepath, "wb") as f:
        f.write(file_bytes)
    print(f"[+] File successfully decompressed and saved to: {output_filepath}")


def process_file():
    ensure_directory()
    registry_map = load_registry()

    while True:
        filepath = input("\nEnter the absolute path of the file to compress (or 'exit' to return to menu): ").strip()
        if filepath.lower() == 'exit':
            break

        if not os.path.exists(filepath):
            print("[!] Error: File does not exist.")
            continue

        # 1. Convert File to Binary String
        bin_sequence = file_to_binary_string(filepath)
        total_len = len(bin_sequence)
        print(f"[*] Base64 Binary Sequence Length (K-equivalent): {total_len} bits")

        if total_len < 2:
            print("[!] Sequence too short to split.")
            continue

        # 2. Analyze sequence for new n-grams and find missing pieces
        missing_sequences = {}
        splits = []

        for i in tqdm(range(1, total_len), desc="[*] Analyzing sequence for new n-grams..."):
            p1 = bin_sequence[:i]
            p2 = bin_sequence[i:]
            splits.append((p1, p2))

            for seq in (p1, p2):
                if seq not in registry_map:
                    k = len(seq)
                    if k not in missing_sequences:
                        missing_sequences[k] = set()
                    missing_sequences[k].add(seq)

        # 3. Curate Registry (Add missing sequences)
        new_items_added = sum(len(seqs) for seqs in missing_sequences.values())
        curation_start = time.time()

        if new_items_added > 0:
            for k, seqs in missing_sequences.items():
                filename = f"registry_k{k}.csv"
                filepath = os.path.join(STORE_DIR, filename)
                file_exists = os.path.exists(filepath)

                row_idx = get_next_row_index(filepath)

                with open(filepath, 'a', newline='') as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(["Row_Index", "SHA256_Hash", "Binary_Sequence"])

                    for seq in seqs:
                        h_val = hashlib.sha256(seq.encode()).hexdigest()
                        writer.writerow([row_idx, h_val, seq])
                        registry_map[seq] = (filename, row_idx, h_val)
                        row_idx += 1

            curation_end = time.time()
            log_curation_time(curation_end - curation_start, new_items_added)
            print(f"[+] Registry updated. {new_items_added} new sequences added.")
        else:
            print("[+] No new sequences needed; all parts already in registry.")

        print(f"[*] Binary registry output path: {os.path.abspath(STORE_DIR)}")

        # 4. Generate Solution Set
        epoch_time = int(time.time())
        solution_filename = f"solution_{epoch_time}.csv"

        print(f"[*] Generating solution set {solution_filename}...")

        with open(solution_filename, 'w', newline='') as f:
            headers = ["Index", "P1_Len", "P1_Preview", "P1_Source", "P1_Row", "P1_Hash",
                       "P2_Len", "P2_Preview", "P2_Source", "P2_Row", "P2_Hash"]
            writer = csv.DictWriter(f, fieldnames=headers, delimiter='\t')
            writer.writeheader()

            preview_rows = []

            for idx, (p1, p2) in enumerate(splits, start=1):
                p1_loc = registry_map[p1]
                p2_loc = registry_map[p2]

                row_data = {
                    "Index": idx,
                    "P1_Len": len(p1),
                    "P1_Preview": p1 if len(p1) <= 32 else f"{p1[:32]}...",
                    "P1_Source": p1_loc,
                    "P1_Row": p1_loc,
                    "P1_Hash": p1_loc,
                    "P2_Len": len(p2),
                    "P2_Preview": p2 if len(p2) <= 32 else f"{p2[:32]}...",
                    "P2_Source": p2_loc,
                    "P2_Row": p2_loc,
                    "P2_Hash": p2_loc,
                }
                writer.writerow(row_data)
                if idx <= 5:
                    preview_rows.append(row_data)

        # 5. Show Preview
        print("\n--- SOLUTION SET PREVIEW ---")
        header_str = "\t".join(headers)
        print(header_str)
        for r in preview_rows:
            row_str = "\t".join(str(r[h]) for h in headers)
            print(row_str)
        if len(splits) > 5:
            print(f"... and {len(splits) - 5} more rows saved to {solution_filename}\n")


def decompress_solution():
    """Decompresses an original file using a solution file and the bidict inverse lookup."""
    ensure_directory()
    registry_map = load_registry()

    # We invert the map to locate binary keys from their file details and hashes.
    # Inverse map structure looks like: registry_map.inv[(filename, row_index, hash)] -> binary_sequence
    inverse_registry = registry_map.inv

    solution_path = input("\nEnter the path to the solution TSV file to decompress: ").strip()
    if not os.path.exists(solution_path):
        print("[!] Error: Solution file not found.")
        return

    row_choice = input("Enter the solution Index row to use for reconstruction (e.g., 1): ").strip()

    try:
        with open(solution_path, 'r', newline='') as f:
            reader = csv.DictReader(f, delimiter='\t')
            target_row = None
            for row in reader:
                if row['Index'] == row_choice:
                    target_row = row
                    break

            if not target_row:
                print(f"[!] Error: Index row {row_choice} not found in the solution file.")
                return

            print(f"[*] Reconstructing split sequence using inverse bidict tokens...")

            # Reconstruct P1 tracking metadata key
            p1_key = (target_row['P1_Source'], int(target_row['P1_Row']), target_row['P1_Hash'])
            # Reconstruct P2 tracking metadata key
            p2_key = (target_row['P2_Source'], int(target_row['P2_Row']), target_row['P2_Hash'])

            # Fetch the actual strings from the registry using bidict's .inv feature
            if p1_key not in inverse_registry or p2_key not in inverse_registry:
                print("[!] Error: The sequences listed in this solution are missing from the current registry store.")
                return

            p1_binary = inverse_registry[p1_key]
            p2_binary = inverse_registry[p2_key]

            # Stitch them back together
            full_binary_sequence = p1_binary + p2_binary

            out_name = input("Enter the output absolute path + name for the recovered file: ").strip()
            binary_string_to_file(full_binary_sequence, out_name)

    except Exception as e:
        print(f"[!] Failed during decompression tracking: {e}")


if __name__ == "__main__":
    while True:
        print("\n--- DYNAMIC ASYMMETRIC REGISTRY HUB ---")
        print("1. Compress and Curate a File")
        print("2. Decompress File using Solution Set")
        print("3. Exit")
        choice = input("Select an option (1-3): ").strip()

        try:
            if choice == '1':
                process_file()
            elif choice == '2':
                decompress_solution()
            elif choice == '3':
                print("[*] Exiting system safely.")
                break
            else:
                print("[!] Invalid option. Try again.")
        except KeyboardInterrupt:
            print("\n[!] Process safely aborted by user.")
            break
        except Exception as e:
            print(f"\n[!] Unexpected Main Error: {e}")