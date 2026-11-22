
from functools import lru_cache


def to_minutes(value):
    """Convert HH:MM or a datetime-like value to minutes after midnight."""
    if value is None or value == "":
        return None

    if hasattr(value, "hour") and hasattr(value, "minute"):
        return value.hour * 60 + value.minute

    hours, minutes = str(value).strip().split(":")
    return int(hours) * 60 + int(minutes)


def format_time(minutes):
    if minutes is None:
        return None

    return f"{int(minutes) // 60:02d}:{int(minutes) % 60:02d}"


def customer_impact_penalty(delay):
    """Illustrative penalty weights; calibrate with real operational data."""
    if delay == 0:
        return 0
    elif delay <= 5:
        return 1
    elif delay <= 10:
        return 3
    elif delay <= 15:
        return 12
    else:
        return 25


def get_kitchen_state(orders, stations, current_time):
    station_names = list(stations.keys())

    station_availability = []

    for station in station_names:
        available_at = to_minutes(
            stations[station].get("available_at")
        )

        if available_at is None:
            available_at = current_time

        station_availability.append(
            max(current_time, available_at)
        )

    active_results = []
    queued_orders = []
    occupied_stations = set()

    for order in orders:
        order_state = order.get("status", "Queued")

        if order_state == "Preparing":
            station = order.get("station")

            if station not in stations:
                raise ValueError(
                    f"Invalid station for order {order['order_id']}"
                )

            if station in occupied_stations:
                raise ValueError(
                    f"Multiple preparing orders assigned to station {station}"
                )

            occupied_stations.add(station)
            station_index = station_names.index(station)

            start = to_minutes(order.get("prep_started_at"))

            if start is None:
                raise ValueError(
                    f"Missing prep_started_at for {order['order_id']}"
                )

            prep_time = int(order["prep_time"])
            deadline = to_minutes(order["committed_time"])

            elapsed = max(0, current_time - start)
            remaining = max(0, prep_time - elapsed)
            completion = current_time + remaining

            delay = max(0, completion - deadline)

            station_availability[station_index] = max(
                station_availability[station_index],
                completion
            )

            active_results.append({
                "order_id": order["order_id"],
                "brand": order["brand"],
                "aggregator": order["aggregator"],
                "Order State": "Preparing",
                "Station": station,
                "Start": format_time(start),
                "Completion": format_time(completion),
                "Deadline": format_time(deadline),
                "Delay": delay,
                "Penalty": customer_impact_penalty(delay),
                "Status": "On Time" if delay == 0 else "Late"
            })

        elif order_state == "Ready":
            active_results.append({
                "order_id": order["order_id"],
                "brand": order["brand"],
                "aggregator": order["aggregator"],
                "Order State": "Ready",
                "Station": order.get("station", ""),
                "Start": None,
                "Completion": None,
                "Deadline": format_time(
                    to_minutes(order["committed_time"])
                ),
                "Delay": 0,
                "Penalty": 0,
                "Status": "Ready"
            })

        else:
            queued_orders.append(order)

    return (
        station_names,
        tuple(station_availability),
        active_results,
        queued_orders
    )


def schedule_orders(
    orders,
    stations,
    current_time="12:20",
    strategy="on_time_first"
):
    """
    Exact scheduling search using memoisation.

    on_time_first:
        Maximise on-time orders, then minimise penalty.

    penalty_first:
        Minimise total customer penalty, then total delay.

    balanced:
        Minimise the worst individual delay, then total penalty,
        then maximise on-time orders.
    """

    valid_strategies = (
        "on_time_first",
        "penalty_first",
        "balanced"
    )

    if strategy not in valid_strategies:
        raise ValueError(
            f"Strategy must be one of: {', '.join(valid_strategies)}"
        )

    current_time = to_minutes(current_time)

    (
        station_names,
        initial_availability,
        active_results,
        queued_orders
    ) = get_kitchen_state(orders, stations, current_time)

    prepared_orders = []

    for order in queued_orders:
        compatible_indices = tuple(
            index
            for index, station in enumerate(station_names)
            if order["brand"] in stations[station]["brands"]
        )

        prepared_orders.append({
            "order": order,
            "arrival": max(
                current_time,
                to_minutes(order["order_time"])
            ),
            "deadline": to_minutes(order["committed_time"]),
            "prep_time": int(order["prep_time"]),
            "compatible": compatible_indices
        })

    unassignable = [
        index
        for index, item in enumerate(prepared_orders)
        if not item["compatible"]
    ]

    assignable = [
        index
        for index, item in enumerate(prepared_orders)
        if item["compatible"]
    ]

    @lru_cache(maxsize=None)
    def solve(remaining_mask, availability):
        """
        Return:
        on_time, penalty, total_delay, max_delay, makespan, schedule
        """

        if remaining_mask == 0:
            return 0, 0, 0, 0, current_time, ()

        best_result = None
        best_score = None

        for order_index in assignable:
            if not (remaining_mask & (1 << order_index)):
                continue

            item = prepared_orders[order_index]

            for station_index in item["compatible"]:
                start = max(
                    item["arrival"],
                    availability[station_index]
                )

                completion = start + item["prep_time"]

                delay = max(
                    0,
                    completion - item["deadline"]
                )

                penalty = customer_impact_penalty(delay)

                new_availability = list(availability)
                new_availability[station_index] = completion

                new_mask = remaining_mask & ~(1 << order_index)

                (
                    future_on_time,
                    future_penalty,
                    future_total_delay,
                    future_max_delay,
                    future_makespan,
                    future_schedule
                ) = solve(
                    new_mask,
                    tuple(new_availability)
                )

                total_on_time = future_on_time + int(delay == 0)
                total_penalty = future_penalty + penalty
                total_delay = future_total_delay + delay
                max_delay = max(future_max_delay, delay)
                makespan = max(future_makespan, completion)

                schedule_entry = (
                    order_index,
                    station_index,
                    start,
                    completion,
                    delay,
                    penalty
                )

                schedule = (schedule_entry,) + future_schedule

                if strategy == "on_time_first":
                    score = (
                        -total_on_time,
                        total_penalty,
                        max_delay,
                        total_delay,
                        makespan
                    )

                elif strategy == "penalty_first":
                    score = (
                        total_penalty,
                        total_delay,
                        -total_on_time,
                        max_delay,
                        makespan
                    )

                else:
                    score = (
                        max_delay,
                        total_penalty,
                        -total_on_time,
                        total_delay,
                        makespan
                    )

                if best_score is None or score < best_score:
                    best_score = score

                    best_result = (
                        total_on_time,
                        total_penalty,
                        total_delay,
                        max_delay,
                        makespan,
                        schedule
                    )

        return best_result

    initial_mask = sum(
        1 << index for index in assignable
    )

    best = solve(initial_mask, initial_availability)

    scheduled_results = []

    if best is not None:
        for (
            order_index,
            station_index,
            start,
            completion,
            delay,
            penalty
        ) in best[5]:

            order = prepared_orders[order_index]["order"]

            scheduled_results.append({
                "order_id": order["order_id"],
                "brand": order["brand"],
                "aggregator": order["aggregator"],
                "Order State": "Queued",
                "Station": station_names[station_index],
                "Start": format_time(start),
                "Completion": format_time(completion),
                "Deadline": format_time(
                    prepared_orders[order_index]["deadline"]
                ),
                "Delay": delay,
                "Penalty": penalty,
                "Status": "On Time" if delay == 0 else "Late"
            })

    for order_index in unassignable:
        order = prepared_orders[order_index]["order"]

        scheduled_results.append({
            "order_id": order["order_id"],
            "brand": order["brand"],
            "aggregator": order["aggregator"],
            "Order State": "Queued",
            "Station": "Unassigned",
            "Start": None,
            "Completion": None,
            "Deadline": format_time(
                prepared_orders[order_index]["deadline"]
            ),
            "Delay": None,
            "Penalty": None,
            "Status": "No feasible station allocation"
        })

    all_results = active_results + scheduled_results

    original_order = {
        order["order_id"]: index
        for index, order in enumerate(orders)
    }

    all_results.sort(
        key=lambda result: original_order[result["order_id"]]
    )

    return all_results
