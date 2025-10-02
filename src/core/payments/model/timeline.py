from enum import Enum

class Timeline(str, Enum):
    TODAY = "TODAY"
    THIS_WEEK = "THIS_WEEK"
    THIS_MONTH = "THIS_MONTH"
    THIS_YEAR = "THIS_YEAR"
    ALL = "ALL"
