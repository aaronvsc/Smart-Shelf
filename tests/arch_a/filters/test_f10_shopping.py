from smart_shelf.arch_a.filters import ShoppingListFilter
from smart_shelf.arch_a.records import Gap


def test_lists_items_to_buy_in_recipe_order(run_filter, make_ctx, make_record):
    r = make_record("F002")
    r.to_buy = [Gap("peanut butter", 32, 32, "g", True, False),
                Gap("soy sauce", 30, 30, "ml", True, False)]
    [out] = run_filter(ShoppingListFilter, [r], make_ctx({"pasta": 500}))
    assert out.shopping_list == ["peanut butter", "soy sauce"]


def test_nothing_to_buy_gives_empty_list(run_filter, make_ctx, make_record):
    [out] = run_filter(ShoppingListFilter, [make_record("F001")], make_ctx({"pasta": 500}))
    assert out.shopping_list == []
