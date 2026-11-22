
import pandas as pd
from pathlib import Path
from scheduler import schedule_orders


# Load orders
project_folder = Path(__file__).resolve().parent.parent
orders_file = project_folder / "data" / "orders.csv"

orders = pd.read_csv(orders_file).to_dict("records")


# Kitchen station configuration
stations = {
    "A": {
        "brands": ["Behrouz", "Oven Story"],
        "available_at": "12:20"
    },
    "B": {
        "brands": ["Faasos", "Oven Story"],
        "available_at": "12:20"
    },
    "C": {
        "brands": ["Faasos", "Behrouz", "Oven Story"],
        "available_at": "12:20"
    }
}


# Test all three strategies
strategies = [
    "on_time_first",
    "penalty_first",
    "balanced"
]

comparison = []

for strategy in strategies:

    results = schedule_orders(
        orders,
        stations,
        current_time="12:20",
        strategy=strategy
    )

    on_time = sum(
        r["Status"] == "On Time" for r in results
    )

    late = sum(
        r["Status"] == "Late" for r in results
    )

    ready = sum(
        r["Order State"] == "Ready" for r in results
    )

    preparing = sum(
        r["Order State"] == "Preparing" for r in results
    )

    unassigned = sum(
        r["Station"] == "Unassigned" for r in results
    )

    total_penalty = sum(
        r["Penalty"] or 0 for r in results
    )

    total_delay = sum(
        r["Delay"] or 0 for r in results
    )

    max_delay = max(
        (r["Delay"] or 0 for r in results),
        default=0
    )

    comparison.append({
        "Strategy": strategy,
        "On Time": on_time,
        "Late": late,
        "Penalty": total_penalty,
        "Total Delay": total_delay,
        "Max Delay": max_delay,
        "Unassigned": unassigned
    })

    print(f"\n--- {strategy.upper()} ---")

    print("Total orders:", len(results))
    print("Preparing:", preparing)
    print("Ready:", ready)
    print("On-time:", on_time)
    print("Late:", late)
    print("Unassigned:", unassigned)
    print("Total customer penalty:", total_penalty)
    print("Total delay:", total_delay)
    print("Maximum individual delay:", max_delay)

    print("\nOrder allocations:")

    for r in results:
        print(
            r["order_id"],
            "| Station:", r["Station"],
            "| Start:", r["Start"],
            "| Completion:", r["Completion"],
            "| Delay:", r["Delay"],
            "| Penalty:", r["Penalty"],
            "| Status:", r["Status"]
        )


# Final comparison
print("\n--- STRATEGY COMPARISON ---")

comparison_df = pd.DataFrame(comparison)

print(comparison_df.to_string(index=False))
