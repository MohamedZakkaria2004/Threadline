"""Illustrative capacity-value arithmetic, never a measured ROI claim."""
from .schemas import BusinessInputs


def calculate(inputs: BusinessInputs):
    a = inputs
    requests = a.employees * a.questions_per_day * a.working_days * a.adoption
    saved_hours = requests * a.usable_answer_rate * a.minutes_saved / 60
    value = saved_hours * a.employee_hourly_usd
    compute_hours = requests * a.inference_seconds / 3600
    electricity = compute_hours * a.power_watts / 1000 * a.electricity_usd_kwh
    support = a.support_hours_monthly * a.developer_hourly_usd
    monthly_cost = support + electricity
    setup = a.build_hours * a.developer_hourly_usd
    net = value - monthly_cost
    year_cost = setup + 12 * monthly_cost
    result = {
        'monthly_requests': requests, 'monthly_hours_saved': saved_hours,
        'monthly_capacity_value_usd': value, 'monthly_compute_hours': compute_hours,
        'monthly_electricity_usd': electricity, 'monthly_support_usd': support,
        'monthly_operating_usd': monthly_cost, 'implementation_usd': setup,
        'monthly_net_value_usd': net, 'first_year_cost_usd': year_cost,
        'first_year_net_value_usd': 12 * value - year_cost,
        'first_year_roi_percent': (12 * value - year_cost) / year_cost * 100 if year_cost else None,
        'payback_months': setup / net if net > 0 else None,
        'sequential_capacity_utilization': compute_hours / (a.working_days * 8),
    }
    return {'assumptions': a.model_dump(), 'results': {k: round(v, 4) if v is not None else None for k, v in result.items()},
            'basis': 'Illustrative capacity value, not cash savings or a measured pilot result. Minutes saved are net of waiting and human review. Existing hardware and zero hosted-model fees assumed; hardware purchase, enterprise integration, tax and benefits realization are excluded.'}


def scenarios():
    return {name: calculate(BusinessInputs(**values)) for name, values in {
        'conservative': {'adoption': 0.25, 'usable_answer_rate': 0.5, 'minutes_saved': 1},
        'base': {},
        'optimistic': {'adoption': 0.75, 'usable_answer_rate': 0.85, 'minutes_saved': 4},
    }.items()}
