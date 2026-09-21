import itertools
import sys
import time
import random
import csv
import os
import tracemalloc
from collections import deque
from datetime import datetime


class SetTransitionEngine:
    def __init__(self, values, length, blacklist=None, gen_method='product', cpu_watts=65.0):
        self.values = values
        self.length = length
        self.blacklist = blacklist if blacklist else []
        self.blacklist_tuples = set(tuple(b) for b in self.blacklist)
        self.gen_method = gen_method
        self.cpu_watts = cpu_watts

        self.min_val = min(values)
        self.max_val = max(values)

        self.possible_states = []
        self.generation_metrics = {}

        self._generate_and_profile()

    def _generate_and_profile(self):
        """Functionality6: Profiles compute, energy, and storage for generating all sets."""
        tracemalloc.start()
        start_ns = time.perf_counter_ns()

        if self.gen_method == 'combinations':
            raw_states = list(itertools.combinations_with_replacement(self.values, self.length))
        else:
            raw_states = list(itertools.product(self.values, repeat=self.length))

        self.possible_states = [list(x) for x in set(raw_states)]
        self.possible_states.sort()

        end_ns = time.perf_counter_ns()
        peak_memory = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()

        compute_ns = end_ns - start_ns
        energy_j = (compute_ns / 1_000_000_000) * self.cpu_watts

        storage_b = peak_memory if peak_memory > 0 else sys.getsizeof(self.possible_states) + sum(
            sys.getsizeof(s) for s in self.possible_states)

        self.generation_metrics = {
            "total": len(self.possible_states),
            "compute_ns": compute_ns,
            "energy_j": energy_j,
            "storage_b": storage_b,
            "method_used": "Combinations" if self.gen_method == 'combinations' else "Permutations"
        }

    def calculate_net_alterations(self, start_state, target_state):
        """
        Functionality11, 13, 18, 50:
        Computes the absolute net delta between start and target.
        Guarantees n-length lists regardless of change. Uses 'Element X' format.
        """
        start_ns = time.perf_counter_ns()
        alterations = []

        for i in range(self.length):
            diff = target_state[i] - start_state[i]
            sign = "+" if diff >= 0 else "-"
            alterations.append(f"Element {i}: {sign}{abs(diff)}")

        end_ns = time.perf_counter_ns()
        compute_ns = end_ns - start_ns
        energy_j = (compute_ns / 1_000_000_000) * self.cpu_watts

        return {
            "alterations": alterations,
            "compute_ns": compute_ns,
            "energy_j": energy_j,
            "storage_b": sys.getsizeof(alterations)
        }

    def _bfs_path(self, start_state, target_state):
        """BFS pathfinding strictly avoiding blacklisted states."""
        queue = deque([(list(start_state), [])])
        visited = set([tuple(start_state)])

        while queue:
            curr, path = queue.popleft()
            if curr == target_state:
                return path

            for i in range(self.length):
                for step_val in [-1, 1]:
                    neighbor = list(curr)
                    neighbor[i] += step_val

                    if neighbor[i] < self.min_val or neighbor[i] > self.max_val:
                        continue

                    t_neighbor = tuple(neighbor)
                    if t_neighbor not in visited and t_neighbor not in self.blacklist_tuples:
                        visited.add(t_neighbor)
                        queue.append((neighbor, path + [(i, step_val, neighbor)]))
        return None

    def calculate_sequential_transition(self, start_state, target_state):
        """Functionality3, 4, 5: Profiles step-by-step sequential routes."""
        tracemalloc.start()
        start_ns = time.perf_counter_ns()

        path_plan = self._bfs_path(start_state, target_state)

        end_ns = time.perf_counter_ns()
        peak_memory = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()

        total_ns = end_ns - start_ns
        total_energy = (total_ns / 1_000_000_000) * self.cpu_watts
        base_storage = peak_memory if peak_memory > 0 else sys.getsizeof(start_state)

        if path_plan is None:
            return {"steps": [{"blocked": True, "target": target_state}],
                    "totals": {"compute_ns": total_ns, "energy_j": total_energy, "storage_b": base_storage}}

        steps = []
        current_state = list(start_state)
        max_storage = base_storage

        step_ns = total_ns // max(1, len(path_plan))
        step_energy = total_energy / max(1, len(path_plan))

        for p in path_plan:
            idx_changed, step_val, _ = p
            current_state[idx_changed] += step_val

            steps.append({
                "blocked": False,
                "start": list(start_state),
                "intermediate": list(current_state),
                "target": target_state,
                "change": f"Element {idx_changed}: {'+1' if step_val > 0 else '-1'}",
                "accomplished": current_state == target_state,
                "energy_j": step_energy,
                "compute_ns": step_ns,
                "storage_b": max_storage
            })

        if not path_plan:
            steps.append({"blocked": False, "intermediate": start_state, "target": target_state, "change": "None",
                          "accomplished": True, "energy_j": 0.0, "compute_ns": 0, "storage_b": max_storage})

        return {"steps": steps, "totals": {"compute_ns": total_ns, "energy_j": total_energy, "storage_b": max_storage}}


def load_csv_data(filepath):
    """Loads array of lists from CSV file (Functionality44, Functionality45)"""
    data = []
    try:
        with open(filepath, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if row:
                    data.append([int(x) for x in row])
        return data
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return []

def run_cli():
    epoch_time = time.time()
    dt_entry = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    folder_name = f"Planner_Output_{int(epoch_time)}"
    os.makedirs(folder_name, exist_ok=True)
    txt_log = []

    def print_and_log(text, end="\n"):
        print(text, end=end)
        txt_log.append(text + end)

    print_and_log("=== RESOURCE-AWARE SET TRANSITION PLANNER ===")

    length_in = input("Enter length of numeric sets (e.g., 3): ")
    print_and_log(f"Enter length of numeric sets (e.g., 3): >? {length_in}")
    length = int(length_in.strip())

    vals_in = input("Enter potential values (e.g., 0 1 2): ")
    print_and_log(f"Enter potential values (e.g., 0 1 2): >? {vals_in}")
    values = [int(v) for v in vals_in.strip().split()]

    watts_in = input("Enter CPU Wattage (e.g., 65.0): ")
    print_and_log(f"Enter CPU Wattage (e.g., 65.0): >? {watts_in}")
    cpu_watts = float(watts_in.strip()) if watts_in.strip() else 65.0

    print_and_log("\n[Functionality37] Set Generation Method (Allows repetition, e.g., [0,0,0]):")
    print_and_log("1. Permutations (Order matters)")
    print_and_log("2. Combinations (Order doesn't matter)")
    gen_choice_in = input("Choice (1/2): ")
    print_and_log(f"Choice (1/2): >? {gen_choice_in}")
    gen_method = 'combinations' if gen_choice_in.strip() == '2' else 'product'

    temp_engine = SetTransitionEngine(values, length, gen_method=gen_method, cpu_watts=cpu_watts)

    print_and_log("\n[Functionality22] Generated Set Preview:")
    preview_limit = 10
    for s in temp_engine.possible_states[:preview_limit]:
        print_and_log(f"  {s}")
    if len(temp_engine.possible_states) > preview_limit:
        print_and_log(f"  ... and {len(temp_engine.possible_states) - preview_limit} more unique sets.")
    print_and_log(f"  (Total Capacity: {len(temp_engine.possible_states)} sets)")

    blacklist = []
    bl_choice_in = input("\n[Functionality7] Specify Blacklist? (y/n/csv): ")
    print_and_log(f"\n[Functionality7] Specify Blacklist? (y/n/csv): >? {bl_choice_in}")
    bl_choice = bl_choice_in.strip().lower()

    if bl_choice == 'y':
        bl_count = int(input("How many blacklisted sets?: ").strip())
        print_and_log(f"How many blacklisted sets?: >? {bl_count}")
        for i in range(bl_count):
            b_in = input(f"Enter blacklist set {i + 1} (space separated): ")
            print_and_log(f"Enter blacklist set {i + 1} (space separated): >? {b_in}")
            blacklist.append([int(x) for x in b_in.strip().split()])
    elif bl_choice == 'csv':
        csv_path = input("Enter Blacklist CSV path: ")
        print_and_log(f"Enter Blacklist CSV path: >? {csv_path}")
        blacklist = load_csv_data(csv_path)

    viable_states = [s for s in temp_engine.possible_states if s not in blacklist]

    print_and_log("\n[Functionality1, 34, & 35] Starting Set Selection:")
    print_and_log("1. One Random")
    print_and_log("2. User-Argument (allow multiple via comma, e.g., 0 1 2, 2 0 1)")
    print_and_log("3. All Viable Generated Sets [Functionality35] (Makes viable paths from ALL items)")
    st_choice_in = input("Choice (1/2/3): ")
    print_and_log(f"Choice (1/2/3): >? {st_choice_in}")
    st_choice = st_choice_in.strip()

    if st_choice == '2':
        st_in = input(f"Enter start sets (comma separated): ")
        print_and_log(f"Enter start sets (comma separated): >? {st_in}")
        start_states = [[int(x) for x in s.split()] for s in st_in.strip().split(',')]
    elif st_choice == '3':
        start_states = [list(x) for x in viable_states]
    else:
        start_states = [list(random.choice(viable_states))] if viable_states else []

    print_and_log("\n[Functionality2, 8, 34, & 35] Target Sets Determination:")
    print_and_log("1. Random (Relegated & Sampled based on quantity)")
    print_and_log("2. User-Argument (allow multiple via comma, e.g., 1 0 2, 0 2 1)")
    print_and_log("3. All Viable Generated Sets [Functionality35] (Creates targets out of all remaining viable sets)")
    print_and_log("4. Import CSV")
    t_choice_in = input("Choice (1/2/3/4): ")
    print_and_log(f"Choice (1/2/3/4): >? {t_choice_in}")
    t_choice = t_choice_in.strip()

    base_targets = []
    target_count = 0

    if t_choice == '1':
        tc_in = input("Enter quantity of targets per start state: ")
        print_and_log(f"Enter quantity of targets per start state: >? {tc_in}")
        target_count = int(tc_in.strip())
        if target_count > len(temp_engine.possible_states):
            raise Exception("Too large a quantity of targets")
        if (target_count + len(blacklist) + 1) > len(temp_engine.possible_states):
            raise Exception(f"[Functionality21] Quantity of required items is greater than generated sets.")
    elif t_choice == '2':
        t_in = input("Enter targets (comma separated): ")
        print_and_log(f"Enter targets (comma separated): >? {t_in}")
        base_targets = [[int(x) for x in s.split()] for s in t_in.strip().split(',')]
    elif t_choice == '3':
        base_targets = viable_states
    elif t_choice == '4':
        t_csv_path = input("Enter Target Sets CSV path: ")
        print_and_log(f"Enter Target Sets CSV path: >? {t_csv_path}")
        base_targets = load_csv_data(t_csv_path)

    print_and_log("\n[Functionality30] Intra-Set Pathing Mode:")
    print_and_log("1. Baton Pass (Continuous Sequence: Target 1's end is Target 2's start)")
    print_and_log("2. Non-Baton Pass (Randomized Relocation: Random new start for each subsequent objective)")
    baton_choice_in = input("Choice (1/2): ")
    print_and_log(f"Choice (1/2): >? {baton_choice_in}")
    is_baton_pass = (baton_choice_in.strip() == '1')

    engine = SetTransitionEngine(values, length, blacklist, gen_method, cpu_watts)

    print_and_log("\n" + "=" * 80)
    print_and_log("[Functionality13] EXPLICIT CONFIGURATION SUMMARY")
    print_and_log("=" * 80)
    print_and_log(f"[Functionality37] Generation Method : {engine.generation_metrics['method_used']}")
    print_and_log(f"[Functionality6] Total Sets Generated : {engine.generation_metrics['total']}")
    print_and_log(f"[Functionality6] Gen Compute (ns)     : {engine.generation_metrics['compute_ns']}")
    print_and_log(f"[Functionality6] Gen Energy (Joules)  : {engine.generation_metrics['energy_j']:.8e}")
    print_and_log(f"[Functionality6] Gen Storage (Bytes)  : {engine.generation_metrics['storage_b']}")
    print_and_log("-" * 80)
    print_and_log(f"Target mode blacklist   : {blacklist if blacklist else 'None'}")
    print_and_log(f"Intra-Set Chaining Mode : {'Baton Pass' if is_baton_pass else 'Non-Baton Pass'}")
    print_and_log("=" * 80 + "\n")

    grand_intra_totals = {"compute_ns": 0, "energy_j": 0.0, "storage_b": 0}
    grand_inter_totals = {"compute_ns": 0, "energy_j": 0.0, "storage_b": 0}

    intra_path_metrics = []
    inter_path_metrics = []
    csv_rows = []

    intra_step_idx = 0
    inter_step_idx = 0

    for start_idx, start_state in enumerate(start_states):
        if t_choice == '1':
            valid_for_this_start = [s for s in viable_states if s != start_state]
            active_targets = random.sample(valid_for_this_start, target_count)
        else:
            active_targets = [t for t in base_targets if t != start_state]

        if not active_targets:
            continue

        print_and_log("\n" + "=" * 80)
        print_and_log(f"PROCESSING STARTING POINT {start_idx + 1}: {start_state}")
        print_and_log("=" * 80)
        print_and_log("Determined Targets:")
        for i, t in enumerate(active_targets):
            print_and_log(f"  Target {i + 1}  : {t}")
        print_and_log("-" * 80)

        # ---------------------------------------------------------
        # INTRA-SET CHANGES
        # ---------------------------------------------------------
        print_and_log(
            f"\n[Functionality9 & 13] INTRA-SET ALTERATIONS (Mode: {'Baton Pass' if is_baton_pass else 'Non-Baton Pass'})")
        print_and_log("-" * 80)

        current_loc = start_state
        intra_header = f"{'Current':<15} | {'Delta Applied':<15} | {'Result State':<15} | {'Metrics (En / Comp / Stor)'}"

        local_intra_totals = {"compute_ns": 0, "energy_j": 0.0, "storage_b": 0}
        full_sequence = [start_state]

        for i, t in enumerate(active_targets):
            if not is_baton_pass and i > 0:
                valid_new_starts = [s for s in engine.possible_states if s != t and s not in blacklist]
                current_loc = random.choice(valid_new_starts) if valid_new_starts else start_state
                full_sequence.append(current_loc)

            print_and_log(f"\nPathing Objective: {current_loc} -> {t}")
            print_and_log("-" * 80)
            print_and_log(intra_header)
            print_and_log("-" * 80)

            result = engine.calculate_sequential_transition(current_loc, t)
            local_intra_totals["compute_ns"] += result["totals"]["compute_ns"]
            local_intra_totals["energy_j"] += result["totals"]["energy_j"]
            local_intra_totals["storage_b"] = max(local_intra_totals["storage_b"], result["totals"]["storage_b"])

            prev_state = current_loc
            for step in result["steps"]:
                intra_step_idx += 1
                if step.get("blocked"):
                    print_and_log(
                        f"{str(prev_state):<15} | {'BLOCKED':<15} | {str(step['target']):<15} | SEQUENCE HALTED")
                    break
                else:
                    metric_str = f"{step['energy_j']:.2e}J / {step['compute_ns']}ns / {step['storage_b']}B"
                    print_and_log(
                        f"{str(prev_state):<15} | {step['change']:<15} | {str(step['intermediate']):<15} | {metric_str}")

                    # Functionality56: Explode row into minute units per element
                    bool_cols = {f"Is_{v}": (v in step['intermediate']) for v in values}
                    base_row_data = {
                        "Date of Entry": dt_entry,
                        "Step_Index": intra_step_idx,
                        "Generated Set": str(engine.possible_states),
                        "Blacklist": str(blacklist),
                        "Target Sets": str(active_targets),
                        "Mode (INTER/INTRA)": "INTRA",
                        "Pathing Objective (Entire Sequence)": " -> ".join([str(x) for x in active_targets]),
                        "Epoch": epoch_time,
                        "Current": str(prev_state),
                        "Delta Applied": step['change'],
                        "Result State": str(step['intermediate']),
                        "Energy (J)": step['energy_j'],
                        "Compute (ns)": step['compute_ns'],
                        "Storage (B)": step['storage_b'],
                        "Measurements": metric_str,
                        "Optimal Resource Displacement Identification": "N/A",
                        "Resource Relegation Summary": "INTRA-STEP",
                        "Best Aggregate Score": 1.0,
                        "Included in Aggregate Pool": "FALSE"
                    }
                    base_row_data.update(bool_cols)

                    for idx_el, val_el in enumerate(step['intermediate']):
                        row_data = base_row_data.copy()
                        row_data["Value"] = val_el
                        row_data["Generated Sequence Set"] = str(step['intermediate'])
                        row_data["Generated Sequence Set Element"] = idx_el
                        csv_rows.append(row_data)

                    prev_state = step['intermediate']

            full_sequence.append(t)

            if result["steps"] and result["steps"][-1].get("blocked") and is_baton_pass:
                break

            if is_baton_pass:
                current_loc = t

        seq_str = " -> ".join([str(x) for x in full_sequence])
        intra_path_metrics.append({
            "path": seq_str,
            "compute_ns": local_intra_totals["compute_ns"],
            "energy_j": local_intra_totals["energy_j"],
            "storage_b": local_intra_totals["storage_b"]
        })
        grand_intra_totals["compute_ns"] += local_intra_totals["compute_ns"]
        grand_intra_totals["energy_j"] += local_intra_totals["energy_j"]
        grand_intra_totals["storage_b"] = max(grand_intra_totals["storage_b"], local_intra_totals["storage_b"])

        # ---------------------------------------------------------
        # INTER-SET CHANGES
        # ---------------------------------------------------------
        print_and_log(f"\n[Functionality11, 13 & 28] INTER-SET DELTAS (Hub & Spoke Model)")
        print_and_log("-" * 80)

        inter_header = f"{'Transition':<25} | {'Net Deltas (Operations)':<35} | {'Metrics'}"
        print_and_log(inter_header)
        print_and_log("-" * len(inter_header))

        for idx, t in enumerate(active_targets):
            result = engine.calculate_net_alterations(start_state, t)

            path_str = f"{start_state} -> {t}"
            inter_path_metrics.append({
                "path": path_str,
                "compute_ns": result["compute_ns"],
                "energy_j": result["energy_j"],
                "storage_b": result["storage_b"]
            })

            grand_inter_totals["compute_ns"] += result["compute_ns"]
            grand_inter_totals["energy_j"] += result["energy_j"]
            grand_inter_totals["storage_b"] = max(grand_inter_totals["storage_b"], result["storage_b"])

            delta_str = ", ".join(result["alterations"])
            metric_str = f"{result['energy_j']:.2e}J / {result['compute_ns']}ns / {result['storage_b']}B"
            print_and_log(f"{str(start_state)} -> {str(t):<11} | {delta_str:<35} | {metric_str}")

            inter_step_idx += 1

            # Functionality56: Explode row into minute units per element
            bool_cols = {f"Is_{v}": (v in t) for v in values}
            base_row_data = {
                "Date of Entry": dt_entry,
                "Step_Index": inter_step_idx,
                "Generated Set": str(engine.possible_states),
                "Blacklist": str(blacklist),
                "Target Sets": str(active_targets),
                "Mode (INTER/INTRA)": "INTER",
                "Pathing Objective (Entire Sequence)": path_str,
                "Epoch": epoch_time,
                "Current": str(start_state),
                "Delta Applied": delta_str,
                "Result State": str(t),
                "Energy (J)": result['energy_j'],
                "Compute (ns)": result['compute_ns'],
                "Storage (B)": result['storage_b'],
                "Measurements": metric_str,
                "Optimal Resource Displacement Identification": "N/A",
                "Resource Relegation Summary": "INTER-NET",
                "Best Aggregate Score": 1.0,
                "Included in Aggregate Pool": "FALSE"
            }
            base_row_data.update(bool_cols)

            for idx_el, val_el in enumerate(t):
                row_data = base_row_data.copy()
                row_data["Value"] = val_el
                row_data["Generated Sequence Set"] = str(t)
                row_data["Generated Sequence Set Element"] = idx_el
                csv_rows.append(row_data)

    print_and_log("\n\n" + "=" * 80)
    print_and_log("[Functionality10, 19, 24, 32, 33] RESOURCE RELEGATION SUMMARY")
    print_and_log("=" * 80)
    print_and_log(
        f"{'Path Explored':<105} | {'Method':<8} | {'Compute (ns)':<15} | {'Energy (J)':<15} | {'Storage (B)':<10}")
    print_and_log("-" * 160)

    for path_data in intra_path_metrics:
        print_and_log(
            f"{path_data['path']:<105} | {'INTRA':<8} | {path_data['compute_ns']:<15} | {path_data['energy_j']:<15.8e} | {path_data['storage_b']:<10}")
    print_and_log("-" * 160)
    for path_data in inter_path_metrics:
        print_and_log(
            f"{path_data['path']:<105} | {'INTER':<8} | {path_data['compute_ns']:<15} | {path_data['energy_j']:<15.8e} | {path_data['storage_b']:<10}")

    print_and_log("=" * 160)
    print_and_log(
        f"{'GRAND TOTAL (INTRA)':<105} | {'INTRA':<8} | {grand_intra_totals['compute_ns']:<15} | {grand_intra_totals['energy_j']:<15.8e} | {grand_intra_totals['storage_b']:<10}")
    print_and_log(
        f"{'GRAND TOTAL (INTER)':<105} | {'INTER':<8} | {grand_inter_totals['compute_ns']:<15} | {grand_inter_totals['energy_j']:<15.8e} | {grand_inter_totals['storage_b']:<10}\n")

    # =========================================================
    # OPTIMAL RESOURCE DISPLACEMENT IDENTIFICATION
    # =========================================================
    all_paths = []
    for p in intra_path_metrics:
        all_paths.append({'path': p['path'], 'mode': 'INTRA', 'compute': p['compute_ns'], 'energy': p['energy_j'],
                          'storage': p['storage_b']})
    for p in inter_path_metrics:
        all_paths.append({'path': p['path'], 'mode': 'INTER', 'compute': p['compute_ns'], 'energy': p['energy_j'],
                          'storage': p['storage_b']})

    if all_paths:
        print_and_log("\n" + "=" * 80)
        print_and_log("[Functionality38] OPTIMAL RESOURCE DISPLACEMENT IDENTIFICATION")
        print_and_log("=" * 80)
        print_and_log("Calculating the operational paths resulting in the least displacement of resources:\n")

        min_c = min(p['compute'] for p in all_paths)
        min_e = min(p['energy'] for p in all_paths)
        min_s = min(p['storage'] for p in all_paths)

        max_c = max((p['compute'] for p in all_paths), default=1)
        max_e = max((p['energy'] for p in all_paths), default=1)
        max_s = max((p['storage'] for p in all_paths), default=1)

        max_c = max_c if max_c > 0 else 1
        max_e = max_e if max_e > 0 else 1
        max_s = max_s if max_s > 0 else 1

        for p in all_paths:
            p['agg_score'] = ((p['compute'] / max_c) + (p['energy'] / max_e) + (p['storage'] / max_s)) / 3.0

        min_agg = min(p['agg_score'] for p in all_paths)

        def print_best(category, val, unit, key, fmt=""):
            best = [p for p in all_paths if p[key] == val]
            print_and_log(f"--- Least {category} Displacement: {val:{fmt}}{unit} ---")
            for i, p in enumerate(best):
                if i < 3:
                    print_and_log(f"  [{p['mode']:<5}] {p['path']}")
                elif i == 3:
                    print_and_log(f"  ... and {len(best) - 3} more paths tied.")
                    break
            print_and_log("")

        print_best("Compute", min_c, " ns", "compute")
        print_best("Energy", min_e, " J", "energy", ".4e")
        print_best("Storage", min_s, " B", "storage")

        best_agg = [p for p in all_paths if p['agg_score'] == min_agg]
        print_and_log("--- Best Aggregate Score (Combined Efficiency) ---")
        print_and_log("  Methodology: Calculates the combined normalized score across Energy, Compute,")
        print_and_log("  and Storage. Scale is >0.0 to 1.0 (where 1.0 is maximum displacement).")
        print_and_log(f"  Lowest Aggregate Displacement Score: {min_agg:.4f}\n")

        for row in csv_rows:
            matched_path = next((p for p in all_paths if
                                 p['path'] in row["Pathing Objective (Entire Sequence)"] and p['mode'] == row[
                                     "Mode (INTER/INTRA)"]), None)
            if matched_path:
                row["Best Aggregate Score"] = matched_path['agg_score']
                row["Included in Aggregate Pool"] = "TRUE"

                opts = []
                if matched_path['compute'] == min_c: opts.append("Compute")
                if matched_path['energy'] == min_e: opts.append("Energy")
                if matched_path['storage'] == min_s: opts.append("Storage")
                if matched_path['agg_score'] == min_agg: opts.append("Aggregate")
                if opts:
                    row["Optimal Resource Displacement Identification"] = "Optimal in: " + ", ".join(opts)

    csv_file_path = os.path.join(folder_name, "transition_data_documentation.csv")
    txt_file_path = os.path.join(folder_name, "transition_console_documentation.txt")

    if csv_rows:
        fieldnames = ["Date of Entry", "Value", "Generated Sequence Set", "Generated Sequence Set Element",
                      "Step_Index", "Generated Set", "Blacklist", "Target Sets", "Mode (INTER/INTRA)",
                      "Pathing Objective (Entire Sequence)", "Epoch", "Current",
                      "Delta Applied", "Result State", "Energy (J)", "Compute (ns)", "Storage (B)",
                      "Measurements", "Optimal Resource Displacement Identification", "Resource Relegation Summary",
                      "Best Aggregate Score", "Included in Aggregate Pool"] + [f"Is_{v}" for v in values]

        with open(csv_file_path, mode='w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in csv_rows:
                writer.writerow(row)

    with open(txt_file_path, mode='w') as txtfile:
        txtfile.writelines(txt_log)

    print(f"\n--- Process Complete. Output logged to {csv_file_path} and {txt_file_path} ---")

def debug_run_cli(setting=0):
    epoch_time = time.time()
    dt_entry = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    folder_name = f"Planner_Output_{int(epoch_time)}"
    os.makedirs(folder_name, exist_ok=True)
    txt_log = []

    def print_and_log(text, end="\n"):
        print(text, end=end)
        txt_log.append(text + end)

    print_and_log("=== RESOURCE-AWARE SET TRANSITION PLANNER ===")

    length_in = None
    if setting == 0:
        length_in = str('3')
    if setting == 1:
        length_in = str('3')
    print_and_log(f"Enter length of numeric sets (e.g., 3): >? {length_in}")
    length = int(length_in.strip())
    vals_in = None
    if setting == 0:
        vals_in = '0 1 2'
    if setting == 1:
        vals_in = '0 1'
    print_and_log(f"Enter potential values (e.g., 0 1 2): >? {vals_in}")
    values = [int(v) for v in vals_in.strip().split()]
    watts_in = None
    if setting == 0:
        watts_in = '167'
    if setting == 1:
        watts_in = '65'
    print_and_log(f"Enter CPU Wattage (e.g., 65.0): >? {watts_in}")
    cpu_watts = float(watts_in.strip()) if watts_in.strip() else 65.0
    gen_choice_in = None
    if setting == 0:
        print_and_log("\n[Functionality37] Set Generation Method (Allows repetition, e.g., [0,0,0]):")
        print_and_log("1. Permutations (Order matters)")
        print_and_log("2. Combinations (Order doesn't matter)")
        gen_choice_in = '2'
    if setting == 1:
        print_and_log("\n[Functionality37] Set Generation Method (Allows repetition, e.g., [0,0,0]):")
        print_and_log("1. Permutations (Order matters)")
        print_and_log("2. Combinations (Order doesn't matter)")
        gen_choice_in = '2'
    print_and_log(f"Choice (1/2): >? {gen_choice_in}")
    gen_method = 'combinations' if gen_choice_in.strip() == '2' else 'product'

    temp_engine = SetTransitionEngine(values, length, gen_method=gen_method, cpu_watts=cpu_watts)

    print_and_log("\n[Functionality22] Generated Set Preview:")
    preview_limit = 10
    for s in temp_engine.possible_states[:preview_limit]:
        print_and_log(f"  {s}")
    if len(temp_engine.possible_states) > preview_limit:
        print_and_log(f"  ... and {len(temp_engine.possible_states) - preview_limit} more unique sets.")
    print_and_log(f"  (Total Capacity: {len(temp_engine.possible_states)} sets)")

    blacklist = []
    bl_choice_in = None
    if setting == 0:
        bl_choice_in = 'csv'
    if setting == 1:
        bl_choice_in = 'csv'
    print_and_log(f"\n[Functionality7] Specify Blacklist? (y/n/csv): >? {bl_choice_in}")
    bl_choice = bl_choice_in.strip().lower()

    if bl_choice == 'y':
        bl_count = None
        if setting == 0:
            bl_count = int('1')
        if setting == 1:
            bl_count = int('1')
        print_and_log(f"How many blacklisted sets?: >? {bl_count}")
        for i in range(bl_count):
            b_in = None
            if setting == 0:
                b_in = '0 1 2'
            print_and_log(f"Enter blacklist set {i + 1} (space separated): >? {b_in}")
            blacklist.append([int(x) for x in b_in.strip().split()])
    elif bl_choice == 'csv':
        if setting == 0:
            csv_path = 'blacklist_stseqmak.csv'
        if setting == 1:
            csv_path = 'blacklist_stseqmak.csv'
        print_and_log(f"Enter Blacklist CSV path: >? {csv_path}")
        blacklist = load_csv_data(csv_path)

    viable_states = [s for s in temp_engine.possible_states if s not in blacklist]

    print_and_log("\n[Functionality1, 34, & 35] Starting Set Selection:")
    print_and_log("1. One Random")
    print_and_log("2. User-Argument (allow multiple via comma, e.g., 0 1 2, 2 0 1)")
    print_and_log("3. All Viable Generated Sets [Functionality35] (Makes viable paths from ALL items)")
    st_choice_in = None
    if setting == 0:
        st_choice_in = '3'
    if setting == 1:
        st_choice_in = '3'
    print_and_log(f"Choice (1/2/3): >? {st_choice_in}")
    st_choice = st_choice_in.strip()

    if st_choice == '2':
        st_in = input(f"Enter start sets (comma separated): ")
        print_and_log(f"Enter start sets (comma separated): >? {st_in}")
        start_states = [[int(x) for x in s.split()] for s in st_in.strip().split(',')]
    elif st_choice == '3':
        start_states = [list(x) for x in viable_states]
    else:
        start_states = [list(random.choice(viable_states))] if viable_states else []

    print_and_log("\n[Functionality2, 8, 34, & 35] Target Sets Determination:")
    print_and_log("1. Random (Relegated & Sampled based on quantity)")
    print_and_log("2. User-Argument (allow multiple via comma, e.g., 1 0 2, 0 2 1)")
    print_and_log("3. All Viable Generated Sets [Functionality35] (Creates targets out of all remaining viable sets)")
    print_and_log("4. Import CSV")
    t_choice_in = None
    if setting == 0:
        t_choice_in = '3'
    if setting == 1:
        t_choice_in = '3'
    print_and_log(f"Choice (1/2/3/4): >? {t_choice_in}")
    t_choice = t_choice_in.strip()

    base_targets = []
    target_count = 0

    if t_choice == '1':
        tc_in = None
        if setting == 0:
            tc_in = '1'
        if setting == 1:
            tc_in = '1'
        print_and_log(f"Enter quantity of targets per start state: >? {tc_in}")
        target_count = int(tc_in.strip())
        if target_count > len(temp_engine.possible_states):
            raise Exception("Too large a quantity of targets")
        if (target_count + len(blacklist) + 1) > len(temp_engine.possible_states):
            raise Exception(f"[Functionality21] Quantity of required items is greater than generated sets.")
    elif t_choice == '2':
        tc_in = None
        if setting == 0:
            t_in = '0 2 2'
        print_and_log(f"Enter targets (comma separated): >? {t_in}")
        base_targets = [[int(x) for x in s.split()] for s in t_in.strip().split(',')]
    elif t_choice == '3':
        base_targets = viable_states
    elif t_choice == '4':
        t_csv_path = None
        if setting == 0:
            t_csv_path = 'target_sequences_stseqmak.csv'
        if setting == 1:
            t_csv_path = 'target_sequences_stseqmak.csv'
        print_and_log(f"Enter Target Sets CSV path: >? {t_csv_path}")
        base_targets = load_csv_data(t_csv_path)

    print_and_log("\n[Functionality30] Intra-Set Pathing Mode:")
    print_and_log("1. Baton Pass (Continuous Sequence: Target 1's end is Target 2's start)")
    print_and_log("2. Non-Baton Pass (Randomized Relocation: Random new start for each subsequent objective)")
    baton_choice_in = None
    if setting == 0:
        baton_choice_in = '2'
    if setting == 1:
        baton_choice_in = '1'
    print_and_log(f"Choice (1/2): >? {baton_choice_in}")
    is_baton_pass = (baton_choice_in.strip() == '1')

    engine = SetTransitionEngine(values, length, blacklist, gen_method, cpu_watts)

    print_and_log("\n" + "=" * 80)
    print_and_log("[Functionality13] EXPLICIT CONFIGURATION SUMMARY")
    print_and_log("=" * 80)
    print_and_log(f"[Functionality37] Generation Method : {engine.generation_metrics['method_used']}")
    print_and_log(f"[Functionality6] Total Sets Generated : {engine.generation_metrics['total']}")
    print_and_log(f"[Functionality6] Gen Compute (ns)     : {engine.generation_metrics['compute_ns']}")
    print_and_log(f"[Functionality6] Gen Energy (Joules)  : {engine.generation_metrics['energy_j']:.8e}")
    print_and_log(f"[Functionality6] Gen Storage (Bytes)  : {engine.generation_metrics['storage_b']}")
    print_and_log("-" * 80)
    print_and_log(f"Target mode blacklist   : {blacklist if blacklist else 'None'}")
    print_and_log(f"Intra-Set Chaining Mode : {'Baton Pass' if is_baton_pass else 'Non-Baton Pass'}")
    print_and_log("=" * 80 + "\n")

    grand_intra_totals = {"compute_ns": 0, "energy_j": 0.0, "storage_b": 0}
    grand_inter_totals = {"compute_ns": 0, "energy_j": 0.0, "storage_b": 0}

    intra_path_metrics = []
    inter_path_metrics = []
    csv_rows = []

    intra_step_idx = 0
    inter_step_idx = 0

    for start_idx, start_state in enumerate(start_states):
        if t_choice == '1':
            valid_for_this_start = [s for s in viable_states if s != start_state]
            active_targets = random.sample(valid_for_this_start, target_count)
        else:
            active_targets = [t for t in base_targets if t != start_state]

        if not active_targets:
            continue

        print_and_log("\n" + "=" * 80)
        print_and_log(f"PROCESSING STARTING POINT {start_idx + 1}: {start_state}")
        print_and_log("=" * 80)
        print_and_log("Determined Targets:")
        for i, t in enumerate(active_targets):
            print_and_log(f"  Target {i + 1}  : {t}")
        print_and_log("-" * 80)

        # ---------------------------------------------------------
        # INTRA-SET CHANGES
        # ---------------------------------------------------------
        print_and_log(
            f"\n[Functionality9 & 13] INTRA-SET ALTERATIONS (Mode: {'Baton Pass' if is_baton_pass else 'Non-Baton Pass'})")
        print_and_log("-" * 80)

        current_loc = start_state
        intra_header = f"{'Current':<15} | {'Delta Applied':<15} | {'Result State':<15} | {'Metrics (En / Comp / Stor)'}"

        local_intra_totals = {"compute_ns": 0, "energy_j": 0.0, "storage_b": 0}
        full_sequence = [start_state]

        for i, t in enumerate(active_targets):
            if not is_baton_pass and i > 0:
                valid_new_starts = [s for s in engine.possible_states if s != t and s not in blacklist]
                current_loc = random.choice(valid_new_starts) if valid_new_starts else start_state
                full_sequence.append(current_loc)

            print_and_log(f"\nPathing Objective: {current_loc} -> {t}")
            print_and_log("-" * 80)
            print_and_log(intra_header)
            print_and_log("-" * 80)

            result = engine.calculate_sequential_transition(current_loc, t)
            local_intra_totals["compute_ns"] += result["totals"]["compute_ns"]
            local_intra_totals["energy_j"] += result["totals"]["energy_j"]
            local_intra_totals["storage_b"] = max(local_intra_totals["storage_b"], result["totals"]["storage_b"])

            prev_state = current_loc
            for step in result["steps"]:
                intra_step_idx += 1
                if step.get("blocked"):
                    print_and_log(
                        f"{str(prev_state):<15} | {'BLOCKED':<15} | {str(step['target']):<15} | SEQUENCE HALTED")
                    break
                else:
                    metric_str = f"{step['energy_j']:.2e}J / {step['compute_ns']}ns / {step['storage_b']}B"
                    print_and_log(
                        f"{str(prev_state):<15} | {step['change']:<15} | {str(step['intermediate']):<15} | {metric_str}")

                    # Functionality56: Explode row into minute units per element
                    bool_cols = {f"Is_{v}": (v in step['intermediate']) for v in values}
                    base_row_data = {
                        "Date of Entry": dt_entry,
                        "Step_Index": intra_step_idx,
                        "Generated Set": str(engine.possible_states),
                        "Blacklist": str(blacklist),
                        "Target Sets": str(active_targets),
                        "Mode (INTER/INTRA)": "INTRA",
                        "Pathing Objective (Entire Sequence)": " -> ".join([str(x) for x in active_targets]),
                        "Epoch": epoch_time,
                        "Current": str(prev_state),
                        "Delta Applied": step['change'],
                        "Result State": str(step['intermediate']),
                        "Energy (J)": step['energy_j'],
                        "Compute (ns)": step['compute_ns'],
                        "Storage (B)": step['storage_b'],
                        "Measurements": metric_str,
                        "Optimal Resource Displacement Identification": "N/A",
                        "Resource Relegation Summary": "INTRA-STEP",
                        "Best Aggregate Score": 1.0,
                        "Included in Aggregate Pool": "FALSE"
                    }
                    base_row_data.update(bool_cols)

                    for idx_el, val_el in enumerate(step['intermediate']):
                        row_data = base_row_data.copy()
                        row_data["Value"] = val_el
                        row_data["Generated Sequence Set"] = str(step['intermediate'])
                        row_data["Generated Sequence Set Element"] = idx_el
                        csv_rows.append(row_data)

                    prev_state = step['intermediate']

            full_sequence.append(t)

            if result["steps"] and result["steps"][-1].get("blocked") and is_baton_pass:
                break

            if is_baton_pass:
                current_loc = t

        seq_str = " -> ".join([str(x) for x in full_sequence])
        intra_path_metrics.append({
            "path": seq_str,
            "compute_ns": local_intra_totals["compute_ns"],
            "energy_j": local_intra_totals["energy_j"],
            "storage_b": local_intra_totals["storage_b"]
        })
        grand_intra_totals["compute_ns"] += local_intra_totals["compute_ns"]
        grand_intra_totals["energy_j"] += local_intra_totals["energy_j"]
        grand_intra_totals["storage_b"] = max(grand_intra_totals["storage_b"], local_intra_totals["storage_b"])

        # ---------------------------------------------------------
        # INTER-SET CHANGES
        # ---------------------------------------------------------
        print_and_log(f"\n[Functionality11, 13 & 28] INTER-SET DELTAS (Hub & Spoke Model)")
        print_and_log("-" * 80)

        inter_header = f"{'Transition':<25} | {'Net Deltas (Operations)':<35} | {'Metrics'}"
        print_and_log(inter_header)
        print_and_log("-" * len(inter_header))

        for idx, t in enumerate(active_targets):
            result = engine.calculate_net_alterations(start_state, t)

            path_str = f"{start_state} -> {t}"
            inter_path_metrics.append({
                "path": path_str,
                "compute_ns": result["compute_ns"],
                "energy_j": result["energy_j"],
                "storage_b": result["storage_b"]
            })

            grand_inter_totals["compute_ns"] += result["compute_ns"]
            grand_inter_totals["energy_j"] += result["energy_j"]
            grand_inter_totals["storage_b"] = max(grand_inter_totals["storage_b"], result["storage_b"])

            delta_str = ", ".join(result["alterations"])
            metric_str = f"{result['energy_j']:.2e}J / {result['compute_ns']}ns / {result['storage_b']}B"
            print_and_log(f"{str(start_state)} -> {str(t):<11} | {delta_str:<35} | {metric_str}")

            inter_step_idx += 1

            # Functionality56: Explode row into minute units per element
            bool_cols = {f"Is_{v}": (v in t) for v in values}
            base_row_data = {
                "Date of Entry": dt_entry,
                "Step_Index": inter_step_idx,
                "Generated Set": str(engine.possible_states),
                "Blacklist": str(blacklist),
                "Target Sets": str(active_targets),
                "Mode (INTER/INTRA)": "INTER",
                "Pathing Objective (Entire Sequence)": path_str,
                "Epoch": epoch_time,
                "Current": str(start_state),
                "Delta Applied": delta_str,
                "Result State": str(t),
                "Energy (J)": result['energy_j'],
                "Compute (ns)": result['compute_ns'],
                "Storage (B)": result['storage_b'],
                "Measurements": metric_str,
                "Optimal Resource Displacement Identification": "N/A",
                "Resource Relegation Summary": "INTER-NET",
                "Best Aggregate Score": 1.0,
                "Included in Aggregate Pool": "FALSE"
            }
            base_row_data.update(bool_cols)

            for idx_el, val_el in enumerate(t):
                row_data = base_row_data.copy()
                row_data["Value"] = val_el
                row_data["Generated Sequence Set"] = str(t)
                row_data["Generated Sequence Set Element"] = idx_el
                csv_rows.append(row_data)

    print_and_log("\n\n" + "=" * 80)
    print_and_log("[Functionality10, 19, 24, 32, 33] RESOURCE RELEGATION SUMMARY")
    print_and_log("=" * 80)
    print_and_log(
        f"{'Path Explored':<105} | {'Method':<8} | {'Compute (ns)':<15} | {'Energy (J)':<15} | {'Storage (B)':<10}")
    print_and_log("-" * 160)

    for path_data in intra_path_metrics:
        print_and_log(
            f"{path_data['path']:<105} | {'INTRA':<8} | {path_data['compute_ns']:<15} | {path_data['energy_j']:<15.8e} | {path_data['storage_b']:<10}")
    print_and_log("-" * 160)
    for path_data in inter_path_metrics:
        print_and_log(
            f"{path_data['path']:<105} | {'INTER':<8} | {path_data['compute_ns']:<15} | {path_data['energy_j']:<15.8e} | {path_data['storage_b']:<10}")

    print_and_log("=" * 160)
    print_and_log(
        f"{'GRAND TOTAL (INTRA)':<105} | {'INTRA':<8} | {grand_intra_totals['compute_ns']:<15} | {grand_intra_totals['energy_j']:<15.8e} | {grand_intra_totals['storage_b']:<10}")
    print_and_log(
        f"{'GRAND TOTAL (INTER)':<105} | {'INTER':<8} | {grand_inter_totals['compute_ns']:<15} | {grand_inter_totals['energy_j']:<15.8e} | {grand_inter_totals['storage_b']:<10}\n")

    # =========================================================
    # OPTIMAL RESOURCE DISPLACEMENT IDENTIFICATION
    # =========================================================
    all_paths = []
    for p in intra_path_metrics:
        all_paths.append({'path': p['path'], 'mode': 'INTRA', 'compute': p['compute_ns'], 'energy': p['energy_j'],
                          'storage': p['storage_b']})
    for p in inter_path_metrics:
        all_paths.append({'path': p['path'], 'mode': 'INTER', 'compute': p['compute_ns'], 'energy': p['energy_j'],
                          'storage': p['storage_b']})

    if all_paths:
        print_and_log("\n" + "=" * 80)
        print_and_log("[Functionality38] OPTIMAL RESOURCE DISPLACEMENT IDENTIFICATION")
        print_and_log("=" * 80)
        print_and_log("Calculating the operational paths resulting in the least displacement of resources:\n")

        min_c = min(p['compute'] for p in all_paths)
        min_e = min(p['energy'] for p in all_paths)
        min_s = min(p['storage'] for p in all_paths)

        max_c = max((p['compute'] for p in all_paths), default=1)
        max_e = max((p['energy'] for p in all_paths), default=1)
        max_s = max((p['storage'] for p in all_paths), default=1)

        max_c = max_c if max_c > 0 else 1
        max_e = max_e if max_e > 0 else 1
        max_s = max_s if max_s > 0 else 1

        for p in all_paths:
            p['agg_score'] = ((p['compute'] / max_c) + (p['energy'] / max_e) + (p['storage'] / max_s)) / 3.0

        min_agg = min(p['agg_score'] for p in all_paths)

        def print_best(category, val, unit, key, fmt=""):
            best = [p for p in all_paths if p[key] == val]
            print_and_log(f"--- Least {category} Displacement: {val:{fmt}}{unit} ---")
            for i, p in enumerate(best):
                if i < 3:
                    print_and_log(f"  [{p['mode']:<5}] {p['path']}")
                elif i == 3:
                    print_and_log(f"  ... and {len(best) - 3} more paths tied.")
                    break
            print_and_log("")

        print_best("Compute", min_c, " ns", "compute")
        print_best("Energy", min_e, " J", "energy", ".4e")
        print_best("Storage", min_s, " B", "storage")

        best_agg = [p for p in all_paths if p['agg_score'] == min_agg]
        print_and_log("--- Best Aggregate Score (Combined Efficiency) ---")
        print_and_log("  Methodology: Calculates the combined normalized score across Energy, Compute,")
        print_and_log("  and Storage. Scale is >0.0 to 1.0 (where 1.0 is maximum displacement).")
        print_and_log(f"  Lowest Aggregate Displacement Score: {min_agg:.4f}\n")

        for row in csv_rows:
            matched_path = next((p for p in all_paths if
                                 p['path'] in row["Pathing Objective (Entire Sequence)"] and p['mode'] == row[
                                     "Mode (INTER/INTRA)"]), None)
            if matched_path:
                row["Best Aggregate Score"] = matched_path['agg_score']
                row["Included in Aggregate Pool"] = "TRUE"

                opts = []
                if matched_path['compute'] == min_c: opts.append("Compute")
                if matched_path['energy'] == min_e: opts.append("Energy")
                if matched_path['storage'] == min_s: opts.append("Storage")
                if matched_path['agg_score'] == min_agg: opts.append("Aggregate")
                if opts:
                    row["Optimal Resource Displacement Identification"] = "Optimal in: " + ", ".join(opts)

    csv_file_path = os.path.join(folder_name, "transition_data_documentation.csv")
    txt_file_path = os.path.join(folder_name, "transition_console_documentation.txt")

    if csv_rows:
        fieldnames = ["Date of Entry", "Value", "Generated Sequence Set", "Generated Sequence Set Element",
                      "Step_Index", "Generated Set", "Blacklist", "Target Sets", "Mode (INTER/INTRA)",
                      "Pathing Objective (Entire Sequence)", "Epoch", "Current",
                      "Delta Applied", "Result State", "Energy (J)", "Compute (ns)", "Storage (B)",
                      "Measurements", "Optimal Resource Displacement Identification", "Resource Relegation Summary",
                      "Best Aggregate Score", "Included in Aggregate Pool"] + [f"Is_{v}" for v in values]

        with open(csv_file_path, mode='w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in csv_rows:
                writer.writerow(row)

    with open(txt_file_path, mode='w') as txtfile:
        txtfile.writelines(txt_log)

    print(f"\n--- Process Complete. Output logged to {csv_file_path} and {txt_file_path} ---")

if __name__ == "__main__":
    print("1. Standard")
    print("2. Debug Setting Zeroth")
    print("3. Debug Setting First")
    choice = int(input("Enter choice: "))
    setting = None
    if choice == 1:
        run_cli()
    elif choice == 2:
        setting = 0
        debug_run_cli(setting=setting)
    elif choice == 3:
        setting = 1
        debug_run_cli(setting=setting)
