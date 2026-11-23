"""XP and rank rules. Games award XP for stars; everything else is small and one-time."""

XP_PER_STAR = 25
READ_XP = 5
PROJECT_XP = 15
XP_PER_RANK = 200
RANKS = ["Intern", "Junior engineer", "Engineer", "Senior engineer", "Staff engineer", "Principal engineer", "Architect"]


def rank_index(xp: int) -> int:
    return min(len(RANKS) - 1, xp // XP_PER_RANK)
