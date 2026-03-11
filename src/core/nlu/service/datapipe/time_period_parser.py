"""
Smart time period parser that converts natural language or coded time periods
to exact lookback days and date ranges.
"""

from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple, Union
import re
import logging

logger = logging.getLogger(__name__)


class TimePeriodCode(Enum):
    """Standard coded time periods that AI should return"""
    TODAY = "TODAY"  # 0-1 days
    YESTERDAY = "YESTERDAY"  # 1-2 days
    WEEK_1 = "WEEK_1"  # Last 7 days
    WEEK_2 = "WEEK_2"  # Last 14 days
    MONTH_1 = "MONTH_1"  # Last 30 days
    MONTH_3 = "MONTH_3"  # Last 90 days
    MONTH_6 = "MONTH_6"  # Last 180 days
    YEAR_1 = "YEAR_1"  # Last 365 days
    ALL_TIME = "ALL_TIME"  # No limit
    CUSTOM = "CUSTOM"  # Custom range (requires start/end dates)


# Mapping of period codes to days
PERIOD_DAYS_MAP = {
    TimePeriodCode.TODAY: 1,
    TimePeriodCode.YESTERDAY: 2,
    TimePeriodCode.WEEK_1: 7,
    TimePeriodCode.WEEK_2: 14,
    TimePeriodCode.MONTH_1: 30,
    TimePeriodCode.MONTH_3: 90,
    TimePeriodCode.MONTH_6: 180,
    TimePeriodCode.YEAR_1: 365,
    TimePeriodCode.ALL_TIME: 10000,  # Effectively all time
}


@dataclass
class DateRange:
    """Represents a time period as a date range"""
    start_date: datetime
    end_date: datetime
    days_back: int
    period_code: Optional[str] = None
    confidence: float = 0.9  # How confident the parser is


class TimePeriodParser:
    """Intelligently parse time periods from natural language or codes"""
    
    # Natural language patterns
    PATTERNS = {
        # Today patterns
        r"^(today|this\s+day|current\s+day)$": TimePeriodCode.TODAY,
        
        # Yesterday patterns
        r"^(yesterday|last\s+day)$": TimePeriodCode.YESTERDAY,
        
        # Week patterns
        r"^(last\s+)?(week|7\s+days|this\s+week|past\s+week)$": TimePeriodCode.WEEK_1,
        r"^(past\s+)?2\s+weeks|14\s+days": TimePeriodCode.WEEK_2,
        
        # Month patterns
        r"^(last\s+)?(month|30\s+days|this\s+month|past\s+month)$": TimePeriodCode.MONTH_1,
        r"^(last\s+)?3\s+months|90\s+days": TimePeriodCode.MONTH_3,
        r"^(last\s+)?6\s+months|180\s+days": TimePeriodCode.MONTH_6,
        
        # Year patterns
        r"^(last\s+)?(year|12\s+months|365\s+days|this\s+year|annual)$": TimePeriodCode.YEAR_1,
        
        # All time
        r"^(all\s+time|everything|entire|since\s+creation)$": TimePeriodCode.ALL_TIME,
    }
    
    # Map of numeric patterns (days, weeks, months, years)
    NUMERIC_PATTERNS = {
        r"(\d+)\s*(days?|d)$": lambda x: int(x),
        r"(\d+)\s*(weeks?|w)$": lambda x: int(x) * 7,
        r"(\d+)\s*(months?|m)$": lambda x: int(x) * 30,
        r"(\d+)\s*(years?|y)$": lambda x: int(x) * 365,
    }
    
    @classmethod
    def parse(
        cls,
        time_period: Optional[str],
        reference_date: Optional[datetime] = None
    ) -> Optional[DateRange]:
        """
        Parse a time period string and return a DateRange.
        
        Args:
            time_period: The time period input (natural language, code, or numeric)
            reference_date: Reference date for calculation (defaults to now)
            
        Returns:
            DateRange object with start_date, end_date, days_back, and period_code
        """
        if not time_period:
            logger.warning("Empty time_period provided, defaulting to MONTH_1")
            return cls._create_date_range(TimePeriodCode.MONTH_1, reference_date)
        
        reference_date = reference_date or datetime.utcnow()
        time_period_clean = time_period.strip().lower()
        
        # Try 1: Check if it's already a period code
        period_code = cls._try_period_code(time_period_clean)
        if period_code:
            logger.debug(f"Matched period code: {period_code}")
            return cls._create_date_range(period_code, reference_date)
        
        # Try 2: Check natural language patterns
        period_code = cls._try_pattern_match(time_period_clean)
        if period_code:
            logger.debug(f"Matched natural language pattern: {period_code}")
            return cls._create_date_range(period_code, reference_date)
        
        # Try 3: Check numeric patterns
        days = cls._try_numeric_parse(time_period_clean)
        if days is not None:
            logger.debug(f"Parsed {days} days from numeric pattern")
            return cls._create_date_range_from_days(days, reference_date)
        
        # Fallback: default to last month
        logger.warning(f"Could not parse time_period '{time_period}', defaulting to MONTH_1")
        return cls._create_date_range(TimePeriodCode.MONTH_1, reference_date)
    
    @classmethod
    def _try_period_code(cls, text: str) -> Optional[TimePeriodCode]:
        """Try to match enum period codes"""
        for code in TimePeriodCode:
            if text == code.value.lower():
                return code
        return None
    
    @classmethod
    def _try_pattern_match(cls, text: str) -> Optional[TimePeriodCode]:
        """Try to match natural language patterns"""
        for pattern, code in cls.PATTERNS.items():
            if re.match(pattern, text):
                return code
        return None
    
    @classmethod
    def _try_numeric_parse(cls, text: str) -> Optional[int]:
        """Try to parse numeric patterns like '30 days' or '3 months'"""
        for pattern, converter in cls.NUMERIC_PATTERNS.items():
            match = re.search(pattern, text)
            if match:
                try:
                    value = converter(match.group(1))
                    return value
                except (ValueError, IndexError):
                    continue
        return None
    
    @classmethod
    def _create_date_range(
        cls,
        period_code: TimePeriodCode,
        reference_date: datetime
    ) -> DateRange:
        """Create a DateRange from a period code"""
        days_back = PERIOD_DAYS_MAP.get(period_code, 30)
        return cls._create_date_range_from_days(days_back, reference_date, period_code)
    
    @classmethod
    def _create_date_range_from_days(
        cls,
        days_back: int,
        reference_date: datetime,
        period_code: Optional[TimePeriodCode] = None
    ) -> DateRange:
        """Create a DateRange from a number of days"""
        start_date = reference_date - timedelta(days=days_back)
        return DateRange(
            start_date=start_date,
            end_date=reference_date,
            days_back=days_back,
            period_code=period_code.value if period_code else None,
            confidence=0.9 if period_code else 0.7
        )


# Convenience functions
def parse_time_period(
    time_period: Optional[str],
    reference_date: Optional[datetime] = None
) -> Optional[DateRange]:
    """Parse a time period and return DateRange"""
    return TimePeriodParser.parse(time_period, reference_date)


def get_lookback_days(
    time_period: Optional[str],
    reference_date: Optional[datetime] = None
) -> int:
    """Get number of days to lookback from a time period string"""
    date_range = TimePeriodParser.parse(time_period, reference_date)
    return date_range.days_back if date_range else 30
