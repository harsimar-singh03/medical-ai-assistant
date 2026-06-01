import re

ALL_DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

SHORT_TO_FULL = {
    'mon': 'monday', 'tue': 'tuesday', 'tues': 'tuesday',
    'wed': 'wednesday', 'thu': 'thursday', 'thur': 'thursday',
    'thurs': 'thursday', 'fri': 'friday', 'sat': 'saturday', 'sun': 'sunday'
}

def parse_available_days(days_string):
    days_string = days_string.strip().lower()
    available_days = set()
    except_days = set()

    except_match = re.search(r'except\s+([^)]+)', days_string)
    if except_match:
        except_part = except_match.group(1).strip()
        days_string = re.sub(r'\s*\(?except\s+[^)]+\)?', '', days_string)
        for part in except_part.split(','):
            part = part.strip()
            if part in SHORT_TO_FULL:
                except_days.add(SHORT_TO_FULL[part])
            elif part in ALL_DAYS:
                except_days.add(part)

    parts = days_string.split(',')
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            start, end = part.split('-', 1)
            start_day = SHORT_TO_FULL.get(start.strip(), start.strip())
            end_day = SHORT_TO_FULL.get(end.strip(), end.strip())
            if start_day in ALL_DAYS and end_day in ALL_DAYS:
                start_idx = ALL_DAYS.index(start_day)
                end_idx = ALL_DAYS.index(end_day)
                for i in range(start_idx, end_idx + 1):
                    available_days.add(ALL_DAYS[i])
        else:
            day = SHORT_TO_FULL.get(part, part)
            if day in ALL_DAYS:
                available_days.add(day)

    return available_days - except_days


def parse_time_slots(hours_string):
    slots = []
    parts = hours_string.split(',')
    for part in parts:
        part = part.strip()
        match = re.match(r'(\d{1,2}):(\d{2})\s*(AM|PM)\s*-\s*(\d{1,2}):(\d{2})\s*(AM|PM)', part, re.IGNORECASE)
        if match:
            start_h = int(match.group(1)); start_m = int(match.group(2)); start_ampm = match.group(3).upper()
            end_h = int(match.group(4)); end_m = int(match.group(5)); end_ampm = match.group(6).upper()
            if start_ampm == 'PM' and start_h != 12: start_h += 12
            if start_ampm == 'AM' and start_h == 12: start_h = 0
            if end_ampm == 'PM' and end_h != 12: end_h += 12
            if end_ampm == 'AM' and end_h == 12: end_h = 0
            start_minutes = start_h * 60 + start_m
            end_minutes = end_h * 60 + end_m
            display = f"{match.group(1)}:{match.group(2)} {start_ampm} - {match.group(4)}:{match.group(5)} {end_ampm}"
            slots.append((start_minutes, end_minutes, display))
    return slots


def extract_day_time(user_input):
    user_input = user_input.lower().strip()
    found_day = None
    for day in SHORT_TO_FULL:
        if day in user_input.split():
            found_day = SHORT_TO_FULL[day]
            break
    if not found_day:
        for day in ALL_DAYS:
            if day in user_input:
                found_day = day
                break
    time_pattern = r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)'
    match = re.search(time_pattern, user_input)
    if match:
        hour = int(match.group(1)); minute = match.group(2) or '00'; ampm = match.group(3).upper()
        found_time = f"{hour}:{minute} {ampm}"
    else:
        found_time = None
    return found_day, found_time


def validate_slot(day, time_str, available_days, available_hours):
    if not day:
        return False, "I couldn't understand the day."
    if not time_str:
        return False, "I couldn't understand the time."

    parsed_days = parse_available_days(available_days)
    if not parsed_days:
        return False, "Could not parse doctor's available days."
    if day not in parsed_days:
        day_list = ', '.join(sorted(parsed_days))
        return False, f"{day.capitalize()} is not available. Available days: {day_list}"

    slots = parse_time_slots(available_hours)
    if not slots:
        return False, "Could not parse doctor's available hours."

    match = re.match(r'(\d{1,2}):(\d{2})\s*(AM|PM)', time_str, re.IGNORECASE)
    if not match:
        return False, "Invalid time format."

    hour = int(match.group(1)); minute = int(match.group(2)); ampm = match.group(3).upper()
    if ampm == 'PM' and hour != 12: hour += 12
    if ampm == 'AM' and hour == 12: hour = 0
    user_minutes = hour * 60 + minute

    for start_min, end_min, slot_str in slots:
        if start_min <= user_minutes <= end_min:
            return True, ""

    slot_strings = [s[2] for s in slots]
    return False, f"{time_str} is outside hours. Available slots: {', '.join(slot_strings)}."