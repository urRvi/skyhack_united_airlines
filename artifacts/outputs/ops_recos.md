# Operational Recommendations
These are mapped from statistical drivers to concrete actions.

## Global actions by driver
- **turn_slack** → Pad scheduled ground time on affected turns; pre-position ramp/cleaning; gate change to shorten taxi path.
- **dep_delay_rate_roll28** → Pre-departure buffers and extra pushback crews during peak; de-peaking banks by 5–10 min.
- **arr_delay_rate_roll28** → Tighten inbound connection protection; proactive reaccom for misconnect risk.
- **route_delay_rate_roll28** → Publish playbook for chronic routes (ATC flow times, taxi congestion); set dynamic crew show times.
- **route_cxl_rate_roll28** → Stage spare aircraft/crews; swap to higher reliability fleets.
- **taxi_out_delta** → Shift push windows; request alternate taxi routes; avoid far-end gates at peak.
- **arrivals_same_hour** → Add gate/ramp staffing in that hour; de-peak schedule; prioritize quick-turn gates.
- **ssr_rate** → Pre-board teams and wheelchairs staged; add aisle chairs; extend boarding window by 5 min.
- **transfer_checked_ratio** → Extra transfer-bag runners & belt capacity; SLA for cross-belt moves.
- **special_bag_ratio** → Dedicated oversize belt staffing; early callouts to baggage.
- **is_peak_season** → Seasonal staffing rosters; temporary schedule buffers.
- **red_eye** → Crew/cleaning overlap; quiet-hour taxi coordination.
- **dep_hub_flag** → Hub control-tower alerting & stand re-assignment rules.
- **type_diff_rate** → Targeted training/briefings for the aircraft type; ensure jet-bridge fit/spares.
- **total_seats** → Adjust boarding groups and door staffing for larger gauge.

## Destination-specific priorities (top 10)
- **GRU**: focus on arr_delay_rate_roll28, route_delay_rate_roll28, turn_slack
- **EDI**: focus on dep_delay_rate_roll28, arr_delay_rate_roll28, route_delay_rate_roll28
- **FAT**: focus on arr_delay_rate_roll28, route_delay_rate_roll28, dep_delay_rate_roll28
- **BCN**: focus on arr_delay_rate_roll28, route_delay_rate_roll28, turn_slack
- **MGW**: focus on arr_delay_rate_roll28, route_delay_rate_roll28, turn_slack
- **MXP**: focus on arr_delay_rate_roll28, route_delay_rate_roll28, turn_slack
- **FRA**: focus on dep_delay_rate_roll28, arr_delay_rate_roll28, red_eye
- **RNO**: focus on arr_delay_rate_roll28, route_delay_rate_roll28, dep_delay_rate_roll28
- **SNN**: focus on arr_delay_rate_roll28, route_delay_rate_roll28, dep_delay_rate_roll28
- **LHR**: focus on arr_delay_rate_roll28, red_eye, dep_delay_rate_roll28
