def get_open_obligations(user):
    """Return human-readable descriptions of the user's unfinished obligations.

    An unfinished obligation is participation in an unfinished paid course or
    an exclusion request whose refund has not been completed yet. The
    authorization module refuses to delete an account while this list is not
    empty and shows the reasons to the user.

    The course module has no models yet, so there are no obligations.
    """
    return []
