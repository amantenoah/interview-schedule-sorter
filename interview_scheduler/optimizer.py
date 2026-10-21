"""Continuity-first interview assignment seeded by a fair min-cost flow."""

from __future__ import annotations

import heapq
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from itertools import combinations

from interview_scheduler.errors import SchedulingError
from interview_scheduler.models import Schedule, SlotAssignment, SlotDemand


_MAX_CONTINUITY_EXCHANGE_SIZE = 3


def _name_sort_key(name: str) -> tuple[str, str]:
    return name.casefold(), name


@dataclass(slots=True)
class _Edge:
    destination: int
    reverse_index: int
    capacity: int
    cost: int


class _ResidualNetwork:
    def __init__(self) -> None:
        self.graph: list[list[_Edge]] = []

    def add_node(self) -> int:
        self.graph.append([])
        return len(self.graph) - 1

    def add_edge(self, source: int, destination: int, capacity: int, cost: int) -> tuple[int, int]:
        forward_index = len(self.graph[source])
        reverse_index = len(self.graph[destination])
        self.graph[source].append(_Edge(destination, reverse_index, capacity, cost))
        self.graph[destination].append(_Edge(source, forward_index, 0, -cost))
        return source, forward_index

    def _shortest_path(self, source: int, potentials: list[int]) -> tuple[list[int], list[tuple[int, int] | None]]:
        infinity = 10**40
        distances = [infinity] * len(self.graph)
        previous: list[tuple[int, int] | None] = [None] * len(self.graph)
        distances[source] = 0
        queue = [(0, source)]
        while queue:
            distance, node = heapq.heappop(queue)
            if distance != distances[node]:
                continue
            for edge_index, edge in enumerate(self.graph[node]):
                if edge.capacity <= 0:
                    continue
                candidate = distance + edge.cost + potentials[node] - potentials[edge.destination]
                if candidate < distances[edge.destination]:
                    distances[edge.destination] = candidate
                    previous[edge.destination] = (node, edge_index)
                    heapq.heappush(queue, (candidate, edge.destination))
        for node, distance in enumerate(distances):
            if distance < infinity:
                potentials[node] += distance
        return distances, previous

    def send(self, source: int, sink: int, required_flow: int) -> None:
        potentials = [0] * len(self.graph)
        sent = 0
        while sent < required_flow:
            distances, previous = self._shortest_path(source, potentials)
            if previous[sink] is None:
                raise SchedulingError("The availability constraints cannot produce a complete schedule.")
            augmentation = required_flow - sent
            node = sink
            while node != source:
                prior_node, edge_index = previous[node]  # type: ignore[misc]
                augmentation = min(augmentation, self.graph[prior_node][edge_index].capacity)
                node = prior_node
            node = sink
            while node != source:
                prior_node, edge_index = previous[node]  # type: ignore[misc]
                edge = self.graph[prior_node][edge_index]
                edge.capacity -= augmentation
                self.graph[node][edge.reverse_index].capacity += augmentation
                node = prior_node
            sent += augmentation


def _validate_inputs(
    demands: tuple[SlotDemand, ...], interviewers: tuple[str, ...], team_size: int
) -> tuple[SlotDemand, ...]:
    if team_size < 1:
        raise ValueError("team_size must be positive.")
    if len(interviewers) != len(set(interviewers)):
        raise SchedulingError("Interviewer names must be unique.")
    known = set(interviewers)
    ordered = tuple(sorted(demands, key=lambda demand: (demand.interview_date, demand.time_slot)))
    keys = tuple((demand.interview_date, demand.time_slot) for demand in ordered)
    if len(keys) != len(set(keys)):
        raise SchedulingError("The demand list contains a duplicate date/time slot.")
    for demand in ordered:
        unknown = set(demand.available_interviewers) - known
        if unknown:
            raise SchedulingError(f"Unknown interviewer(s) in availability: {', '.join(sorted(unknown))}.")
    shortages = tuple(demand for demand in ordered if len(set(demand.available_interviewers)) < team_size)
    if shortages:
        details = "; ".join(
            f"{demand.interview_date.strftime('%B')} {demand.interview_date.day} "
            f"({demand.time_slot.label}): {len(set(demand.available_interviewers))} available"
            for demand in shortages
        )
        raise SchedulingError(f"The following interview slots could not be staffed with {team_size} officers: {details}.")
    return ordered


def _objective_weights(demands: tuple[SlotDemand, ...], interviewer_count: int, team_size: int) -> tuple[int, int]:
    required = len(demands) * team_size
    tie_bound = required * max(interviewer_count - 1, 0)
    daily_weight = tie_bound + 1
    daily_slot_counts = Counter(demand.interview_date for demand in demands)
    daily_square_bound = interviewer_count * sum(count * count for count in daily_slot_counts.values())
    global_weight = daily_weight * (daily_square_bound + 1)
    return global_weight, daily_weight


def _availability_counts(
    demands: tuple[SlotDemand, ...], interviewers: tuple[str, ...]
) -> tuple[Counter[str], Counter[tuple[str, date]]]:
    total_counts: Counter[str] = Counter()
    daily_counts: Counter[tuple[str, date]] = Counter()
    for demand in demands:
        for interviewer in set(demand.available_interviewers):
            total_counts[interviewer] += 1
            daily_counts[(interviewer, demand.interview_date)] += 1
    return total_counts, daily_counts


def _build_network(
    demands: tuple[SlotDemand, ...], interviewers: tuple[str, ...], team_size: int
) -> tuple[_ResidualNetwork, int, int, tuple[tuple[int, str, tuple[int, int]], ...]]:
    network = _ResidualNetwork()
    source, sink = network.add_node(), network.add_node()
    interviewer_nodes = {name: network.add_node() for name in interviewers}
    day_nodes = {
        (name, interview_date): network.add_node()
        for name in interviewers
        for interview_date in sorted({demand.interview_date for demand in demands})
    }
    slot_nodes = tuple(network.add_node() for _ in demands)
    global_weight, daily_weight = _objective_weights(demands, len(interviewers), team_size)
    total_availability, daily_availability = _availability_counts(demands, interviewers)

    for name in interviewers:
        for unit in range(1, total_availability[name] + 1):
            network.add_edge(source, interviewer_nodes[name], 1, (2 * unit - 1) * global_weight)
    for (name, interview_date), node in day_nodes.items():
        for unit in range(1, daily_availability[(name, interview_date)] + 1):
            network.add_edge(interviewer_nodes[name], node, 1, (2 * unit - 1) * daily_weight)

    handles = []
    ranks = {name: index for index, name in enumerate(interviewers)}
    for demand_index, demand in enumerate(demands):
        for name in sorted(set(demand.available_interviewers), key=_name_sort_key):
            tie_cost = (ranks[name] - demand_index * team_size) % len(interviewers)
            handle = network.add_edge(day_nodes[(name, demand.interview_date)], slot_nodes[demand_index], 1, tie_cost)
            handles.append((demand_index, name, handle))
        network.add_edge(slot_nodes[demand_index], sink, team_size, 0)
    return network, source, sink, tuple(handles)


def _run_penalty(length: int) -> int:
    """Prefer two/three-slot blocks while retaining value from longer continuity."""

    if length == 1:
        return 3
    if length <= 3:
        return 0
    return length - 1


def _interviewer_continuity_penalty(
    demands: tuple[SlotDemand, ...], teams: tuple[frozenset[str], ...], interviewer: str
) -> int:
    penalty = 0
    run_length = 0
    previous_end: int | None = None
    for demand, team in zip(demands, teams, strict=True):
        assigned = interviewer in team
        adjacent = previous_end == demand.time_slot.start_minutes
        if assigned and run_length and adjacent:
            run_length += 1
        elif assigned:
            penalty += _run_penalty(run_length)
            run_length = 1
        elif run_length:
            penalty += _run_penalty(run_length)
            run_length = 0
        previous_end = demand.time_slot.end_minutes
    return penalty + _run_penalty(run_length)


def _exchange_teams(
    teams: tuple[frozenset[str], ...],
    left_index: int,
    right_index: int,
    leaving_left: frozenset[str],
    leaving_right: frozenset[str],
) -> tuple[frozenset[str], ...]:
    new_left = (teams[left_index] - leaving_left) | leaving_right
    new_right = (teams[right_index] - leaving_right) | leaving_left
    return tuple(
        new_left if index == left_index else new_right if index == right_index else team
        for index, team in enumerate(teams)
    )


def _replace_team_member(
    teams: tuple[frozenset[str], ...],
    index: int,
    outgoing: str,
    incoming: str,
) -> tuple[frozenset[str], ...]:
    replacement = (teams[index] - {outgoing}) | {incoming}
    return tuple(replacement if team_index == index else team for team_index, team in enumerate(teams))


def _day_ranges(demands: tuple[SlotDemand, ...]) -> tuple[tuple[int, int], ...]:
    ranges = []
    day_start = 0
    while day_start < len(demands):
        interview_date = demands[day_start].interview_date
        day_end = day_start + 1
        while day_end < len(demands) and demands[day_end].interview_date == interview_date:
            day_end += 1
        ranges.append((day_start, day_end))
        day_start = day_end
    return tuple(ranges)


def _improve_day_continuity(
    demands: tuple[SlotDemand, ...], teams: tuple[frozenset[str], ...]
) -> tuple[frozenset[str], ...]:
    """Find a deterministic local optimum without changing anyone's daily workload."""

    current = teams
    while True:
        names = frozenset(name for team in current for name in team)
        current_penalties = {
            name: _interviewer_continuity_penalty(demands, current, name) for name in names
        }
        best_improvement = 0
        best_candidate: tuple[frozenset[str], ...] | None = None

        for left_index, right_index in combinations(range(len(demands)), 2):
            left_only = tuple(sorted(current[left_index] - current[right_index], key=_name_sort_key))
            right_only = tuple(sorted(current[right_index] - current[left_index], key=_name_sort_key))
            exchange_limit = min(
                len(left_only),
                len(right_only),
                _MAX_CONTINUITY_EXCHANGE_SIZE,
            )
            left_available = frozenset(demands[left_index].available_interviewers)
            right_available = frozenset(demands[right_index].available_interviewers)

            for exchange_size in range(1, exchange_limit + 1):
                for left_group in combinations(left_only, exchange_size):
                    leaving_left = frozenset(left_group)
                    if not leaving_left <= right_available:
                        continue
                    for right_group in combinations(right_only, exchange_size):
                        leaving_right = frozenset(right_group)
                        if not leaving_right <= left_available:
                            continue
                        affected = leaving_left | leaving_right
                        before = sum(current_penalties[name] for name in affected)
                        candidate = _exchange_teams(
                            current,
                            left_index,
                            right_index,
                            leaving_left,
                            leaving_right,
                        )
                        after = sum(
                            _interviewer_continuity_penalty(demands, candidate, name)
                            for name in affected
                        )
                        improvement = before - after
                        if improvement > best_improvement:
                            best_improvement = improvement
                            best_candidate = candidate

        if best_candidate is None:
            return current
        current = best_candidate


def _improve_continuity(
    demands: tuple[SlotDemand, ...], teams: tuple[frozenset[str], ...]
) -> tuple[frozenset[str], ...]:
    improved = teams
    for day_start, day_end in _day_ranges(demands):
        improved_day = _improve_day_continuity(
            demands[day_start:day_end],
            improved[day_start:day_end],
        )
        improved = improved[:day_start] + improved_day + improved[day_end:]
    return improved


def _assignment_counts(
    demands: tuple[SlotDemand, ...], teams: tuple[frozenset[str], ...]
) -> tuple[Counter[str], Counter[tuple[str, date]]]:
    total_counts: Counter[str] = Counter()
    daily_counts: Counter[tuple[str, date]] = Counter()
    for demand, team in zip(demands, teams, strict=True):
        for name in team:
            total_counts[name] += 1
            daily_counts[(name, demand.interview_date)] += 1
    return total_counts, daily_counts


def _squared_count_delta(outgoing_count: int, incoming_count: int) -> int:
    """Return the sum-of-squares change for one decrement and one increment."""

    return 2 * (incoming_count - outgoing_count + 1)


def _best_continuity_first_replacement(
    demands: tuple[SlotDemand, ...], teams: tuple[frozenset[str], ...]
) -> tuple[tuple[frozenset[str], ...], tuple[int, int]] | None:
    """Choose the best move by continuity, global fairness, then daily fairness."""

    total_counts, daily_counts = _assignment_counts(demands, teams)
    best_delta = (0, 0, 0)
    best_candidate: tuple[frozenset[str], ...] | None = None
    best_day_range: tuple[int, int] | None = None

    for day_start, day_end in _day_ranges(demands):
        day_demands = demands[day_start:day_end]
        day_teams = teams[day_start:day_end]
        relevant_names = frozenset(
            name
            for demand, team in zip(day_demands, day_teams, strict=True)
            for name in set(demand.available_interviewers) | team
        )
        current_penalties = {
            name: _interviewer_continuity_penalty(day_demands, day_teams, name)
            for name in relevant_names
        }
        interview_date = day_demands[0].interview_date

        for local_index, (demand, team) in enumerate(zip(day_demands, day_teams, strict=True)):
            incoming_names = tuple(
                sorted(set(demand.available_interviewers) - team, key=_name_sort_key)
            )
            for outgoing in sorted(team, key=_name_sort_key):
                for incoming in incoming_names:
                    candidate_day = _replace_team_member(
                        day_teams,
                        local_index,
                        outgoing,
                        incoming,
                    )
                    continuity_delta = sum(
                        _interviewer_continuity_penalty(day_demands, candidate_day, name)
                        - current_penalties[name]
                        for name in (outgoing, incoming)
                    )
                    global_fairness_delta = _squared_count_delta(
                        total_counts[outgoing],
                        total_counts[incoming],
                    )
                    daily_fairness_delta = _squared_count_delta(
                        daily_counts[(outgoing, interview_date)],
                        daily_counts[(incoming, interview_date)],
                    )
                    objective_delta = (
                        continuity_delta,
                        global_fairness_delta,
                        daily_fairness_delta,
                    )
                    if objective_delta < best_delta:
                        best_delta = objective_delta
                        best_candidate = (
                            teams[:day_start]
                            + candidate_day
                            + teams[day_end:]
                        )
                        best_day_range = (day_start, day_end)

    if best_candidate is None or best_day_range is None:
        return None
    return best_candidate, best_day_range


def _optimize_continuity_first(
    demands: tuple[SlotDemand, ...], teams: tuple[frozenset[str], ...]
) -> tuple[frozenset[str], ...]:
    current = _improve_continuity(demands, teams)
    while True:
        replacement = _best_continuity_first_replacement(demands, current)
        if replacement is None:
            return current
        current, (day_start, day_end) = replacement
        improved_day = _improve_day_continuity(
            demands[day_start:day_end],
            current[day_start:day_end],
        )
        current = current[:day_start] + improved_day + current[day_end:]


def assign_interviewers(
    demands: tuple[SlotDemand, ...], interviewers: tuple[str, ...], team_size: int = 3
) -> Schedule:
    """Prefer two/three-slot blocks, then global and daily workload fairness."""

    ordered_interviewers = tuple(sorted(interviewers, key=_name_sort_key))
    ordered_demands = _validate_inputs(tuple(demands), ordered_interviewers, team_size)
    if not ordered_demands:
        return Schedule(())
    network, source, sink, handles = _build_network(ordered_demands, ordered_interviewers, team_size)
    network.send(source, sink, len(ordered_demands) * team_size)
    selected: dict[int, list[str]] = defaultdict(list)
    for demand_index, name, (node, edge_index) in handles:
        if network.graph[node][edge_index].capacity == 0:
            selected[demand_index].append(name)
    initial_teams = tuple(frozenset(selected[index]) for index in range(len(ordered_demands)))
    if any(len(team) != team_size for team in initial_teams):
        raise SchedulingError("The optimizer returned an incomplete assignment.")
    improved_teams = _optimize_continuity_first(ordered_demands, initial_teams)
    assignments = tuple(
        SlotAssignment(
            demand.interview_date,
            demand.time_slot,
            tuple(sorted(improved_teams[index], key=_name_sort_key)),
        )
        for index, demand in enumerate(ordered_demands)
    )
    return Schedule(assignments)
