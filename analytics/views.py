from django.shortcuts import render
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound
from django.core.exceptions import ObjectDoesNotExist
from .models import RequestCount
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
import json
import itertools

@staff_member_required
def dashboard(request):
    """Renders the template for the dashboard."""
    return render(request, "analytics/dashboard.html")

def get_time_bounds(time_frame):
    """Translates a time frame string (e.g. "day", "week", "month", "year",
    "all-time") into a minimum time and an interval between times for the
    data collection. Returns (minimum time, interval, format string)."""
    if time_frame == "week":
        early_time = timezone.now() - timezone.timedelta(days=7)
        early_time = early_time.replace(hour=0, minute=0)
        delta = timezone.timedelta(days=1)
        format = "%a, %b %d"
    elif time_frame == "month":
        early_time = timezone.now() - timezone.timedelta(weeks=4)
        early_time = early_time.replace(hour=0, minute=0)
        delta = timezone.timedelta(days=1)
        format = "%b %d"
    elif time_frame == "year":
        early_time = timezone.now() - timezone.timedelta(weeks=52)
        early_time = early_time.replace(hour=0, minute=0)
        delta = timezone.timedelta(weeks=1)
        format = "%b %d, %Y"
    elif time_frame == "all-time":
        try:
            early_time = RequestCount.objects.order_by("timestamp").first().timestamp
            early_time = early_time.replace(minute=0)
            # Try multiple intervals to see what's best
            last_result = None
            test_intervals = [
                (timezone.timedelta(hours=1), "%I %p"),
                (timezone.timedelta(days=1), "%a, %b %d"),
                (timezone.timedelta(weeks=1), "%a, %b %d"),
                (timezone.timedelta(weeks=4), "%b %d, %Y")
            ]
            for interval, format in test_intervals:
                num_bars = (timezone.now() - early_time).seconds / interval.seconds + 1
                last_result = early_time, interval, format
                if 8 <= num_bars <= 15:
                    break
            early_time, delta, format = last_result
            format = "%b %d, %Y"
        except ObjectDoesNotExist:
            early_time = timezone.now() - timezone.timedelta(hours=24)
            early_time = early_time.replace(hour=0, minute=0)
            delta = timezone.timedelta(hours=1)
            format = "%I %p"
    else:
        early_time = timezone.now() - timezone.timedelta(hours=24)
        early_time = early_time.replace(minute=0)
        delta = timezone.timedelta(hours=1)
        format = "%I %p"
    return early_time, delta, format

@staff_member_required
def total_requests(request, time_frame=None):
    """Returns data for the Chart.js chart containing the total number of
    requests over time."""
    early_time, delta, format = get_time_bounds(time_frame)
    data = RequestCount.tabulate_requests(early_time, delta, lambda _: 1)
    labels, counts = itertools.izip(*((t.strftime(format).lstrip("0"), item.get(1, 0)) for t, item in data))
    counts = [item.get(1, 0) for _, item in data]
    return HttpResponse(json.dumps({"labels": labels, "data": counts}), content_type="application/json")

USER_AGENT_TYPES = [
    "Desktop",
    "iOS",
    "Android",
    "Mobile Safari",
    "Android Browser"
]

def translate_user_agent_string(user_agent):
    """Returns the most likely user agent type for the given user agent string."""
    if "CFNetwork" in user_agent:
        return "iOS"
    elif "okhttp" in user_agent:
        return "Android"
    elif "Android" in user_agent:
        return "Android Browser"
    elif "Mobile" in user_agent and "Safari" in user_agent:
        return "Mobile Safari"
    else:
        return "Desktop"

@staff_member_required
def user_agents(request, time_frame=None):
    """Returns data for the Chart.js chart containing the various user agents
    observed over time."""
    early_time, delta, format = get_time_bounds(time_frame)
    data = RequestCount.tabulate_requests(early_time, delta, lambda request: translate_user_agent_string(request.user_agent))
    labels = [t.strftime(format).lstrip("0") for t, _ in data]
    datasets = {agent: [item.get(agent, 0) for _, item in data] for agent in USER_AGENT_TYPES}
    return HttpResponse(json.dumps({"labels": labels, "data": datasets}), content_type="application/json")
