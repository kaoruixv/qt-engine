import argparse
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class DCFScenario:
    name: str
    starting_fcf: float
    growth_rate: float
    discount_rate: float
    terminal_growth_rate: float
    projection_years: int
    shares_outstanding: float
    net_debt: float = 0.0


def calculate_implied_share_price(scenario):
    if scenario.projection_years <= 0:
        raise ValueError("projection_years must be greater than zero.")
    if scenario.shares_outstanding <= 0:
        raise ValueError("shares_outstanding must be greater than zero.")
    if scenario.discount_rate <= scenario.terminal_growth_rate:
        raise ValueError("discount_rate must be greater than terminal_growth_rate.")

    discounted_fcf = 0.0
    final_year_fcf = scenario.starting_fcf

    for year in range(1, scenario.projection_years + 1):
        final_year_fcf = scenario.starting_fcf * ((1 + scenario.growth_rate) ** year)
        discounted_fcf += final_year_fcf / ((1 + scenario.discount_rate) ** year)

    terminal_value = (
        final_year_fcf
        * (1 + scenario.terminal_growth_rate)
        / (scenario.discount_rate - scenario.terminal_growth_rate)
    )
    discounted_terminal_value = terminal_value / ((1 + scenario.discount_rate) ** scenario.projection_years)
    enterprise_value = discounted_fcf + discounted_terminal_value
    equity_value = enterprise_value - scenario.net_debt

    return equity_value / scenario.shares_outstanding


def analyze_scenarios(scenarios):
    required_names = {"bear", "base", "bull"}
    missing = required_names - set(scenarios)
    if missing:
        raise ValueError(f"Missing required scenario(s): {', '.join(sorted(missing))}")

    results = {}
    for name in ("bear", "base", "bull"):
        scenario = scenarios[name]
        results[name] = calculate_implied_share_price(scenario)

    return results


def load_scenarios(path):
    with open(path) as f:
        payload = json.load(f)

    raw_scenarios = payload.get("scenarios", payload)
    return {
        name: DCFScenario(name=name, **assumptions)
        for name, assumptions in raw_scenarios.items()
    }


def print_results(results):
    print("--- DCF SCENARIO ANALYSIS ---")
    for name in ("bear", "base", "bull"):
        print(f"{name.title():>4} implied share price: ${results[name]:,.2f}")


def main():
    parser = argparse.ArgumentParser(description="Run bear/base/bull DCF scenario analysis.")
    parser.add_argument("input_json", help="Path to a JSON file containing bear/base/bull DCF assumptions.")
    args = parser.parse_args()

    scenarios = load_scenarios(args.input_json)
    results = analyze_scenarios(scenarios)
    print_results(results)


if __name__ == "__main__":
    main()
