from .models import RollLink


def roll_link_counts(request):
    """顶栏未关闭揉捻衔接单数：与衔接列表的未关闭计数同一查询口径。"""
    if not request.user.is_authenticated:
        return {"open_roll_link_count": 0}
    return {
        "open_roll_link_count": RollLink.objects.filter(
            closedAt__isnull=True
        ).count()
    }
