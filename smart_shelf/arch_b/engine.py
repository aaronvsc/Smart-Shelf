"""Public session API for Aaron's shared Streamlit UI."""
from __future__ import annotations

import time
from datetime import date
from pathlib import Path
from typing import Callable, Iterable

from smart_shelf.common.data_access import load_profile, save_selection
from smart_shelf.common.models import ReferenceData, UserProfile

from .blackboard import Blackboard
from .controller import Controller, ControllerError
from .knowledge_sources import SelectionRequest, default_sources
from .models import BlackboardResult, ExclusionSummary


class BlackboardEngine:
    """Keep one engine per user in Streamlit session_state.

    run() starts a fresh pantry analysis; decide_substitute() updates only the
    affected regions. select() is an explicit history-writing action. Its event
    ID must be reused for rerenders of the same user click, and changed for a
    new cooking selection, even if the same recipes are picked again.
    """

    def __init__(self, ref: ReferenceData, profiles_dir: Path | None = None,
                 selection_writer: Callable | None = None):
        self.ref = ref
        def persist(profile, request):
            current = load_profile(profile.user_id, profiles_dir)
            if (current.restrictions, current.allergies) != (profile.restrictions, profile.allergies):
                raise ValueError("Profile restrictions changed; reload the profile and rerun the pantry")
            return save_selection(profile.user_id, list(request.recipe_ids), request.on, profiles_dir)

        self._writer = selection_writer or persist
        self._saved: dict[tuple[str, str], tuple[SelectionRequest, UserProfile]] = {}
        self.board = Blackboard()
        self.controller = Controller(self.board, default_sources(ref, self._save_once))

    def _save_once(self, profile, request):
        key = (profile.user_id, request.event_id)
        if key in self._saved:
            original, updated = self._saved[key]
            if original != request:
                raise ValueError("A selection event ID cannot be reused with different selections or dates")
            return updated
        updated = self._writer(profile, request)
        if not isinstance(updated, UserProfile) or updated.user_id != profile.user_id:
            raise ValueError("Selection writer must return the same user's updated profile")
        if (updated.restrictions, updated.allergies) != (profile.restrictions, profile.allergies):
            raise ValueError("Profile restrictions changed; reload the profile and rerun the pantry")
        self._saved[key] = (request, updated)
        return updated

    def run(self, raw_pantry: list[dict], profile: UserProfile | None,
            rejected_subs: Iterable[tuple[str, str]] = (), today: date | None = None):
        start = time.perf_counter()
        if profile is None:
            raise ValueError("A user profile is required; refusing to run without restrictions")
        self.ref.check_restrictions(profile)
        if not isinstance(raw_pantry, list):
            raise ValueError("Pantry input must be a list of rows")
        rejected = frozenset(tuple(pair) for pair in rejected_subs)
        if any(len(pair) != 2 for pair in rejected):
            raise ValueError("Rejected substitutes must be (recipe_id, substitute_name) pairs")
        self.board = Blackboard()
        self.controller = Controller(self.board, default_sources(self.ref, self._save_once))
        self.board.publish(raw_pantry=raw_pantry, profile=profile,
                           rejected_subs=rejected, today=today or date.today(),
                           selected_ids=(), selection_request=None)
        result = self._execute()
        result.elapsed_s = time.perf_counter() - start
        return result

    def _require_run(self):
        if not self.board.has("raw_pantry", "profile"):
            raise ValueError("Call run() with a pantry and profile first")

    def decide_substitute(self, recipe_id: str, substitute_name: str, accepted: bool):
        self._require_run()
        if not self.board.has("gaps"):
            raise ValueError("No candidate recipes are available for substitution")
        if not isinstance(accepted, bool):
            raise ValueError("accepted must be True or False")
        records = self.board.read("gaps")
        record = next((record for record in records if record.recipe.id == recipe_id), None)
        if record is None or not any(
            gap.required and gap.substitutable and any(
                sub.name == substitute_name for sub in self.ref.substitutes.get(gap.name, ()))
            for gap in record.missing
        ):
            raise ValueError("Substitute decision does not refer to a candidate recipe's gap")
        rejected = set(self.board.read("rejected_subs"))
        pair = (recipe_id, substitute_name)
        if accepted:
            rejected.discard(pair)
        else:
            rejected.add(pair)
        self.board.publish(rejected_subs=frozenset(rejected))
        return self._execute()

    def select(self, recipe_ids: Iterable[str], event_id: str, on: date | None = None):
        self._require_run()
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("A nonempty selection event ID is required")
        ids = tuple(sorted(set(recipe_ids)))
        if not self.board.has("dietary", "candidates"):
            raise ValueError("No candidate recipes are available for selection")
        dietary = self.board.read("dietary")
        allowed = {recipe.id for recipe in self.board.read("candidates") if not dietary[recipe.id]}
        if not ids or not set(ids) <= allowed:
            raise ValueError("Select at least one recipe from the allowed ranked results")
        request = SelectionRequest(event_id, ids, on or self.board.read("today"))
        profile = self.board.read("profile")
        key = (profile.user_id, event_id)
        if key in self._saved:
            if self._saved[key][0] != request:
                raise ValueError("A selection event ID cannot be reused with different selections or dates")
            # A rerender of a completed click cannot undo a later selection.
            return self._execute()
        self.board.publish(selected_ids=ids, selection_request=request)
        return self._execute()

    def _execute(self):
        start = time.perf_counter()
        activations = self.controller.run()
        if self.board.has("pantry", "unrecognized") and not self.board.read("pantry"):
            return BlackboardResult("empty_pantry", unrecognized=self.board.read("unrecognized"),
                                    elapsed_s=time.perf_counter() - start, activations=activations)
        if not self.board.has("shopping", "combined_shopping", "unrecognized", "dietary"):
            raise ControllerError("Incomplete analysis; refusing to expose stale results")
        ranked = self.board.read("shopping")
        dietary = self.board.read("dietary")
        excluded = {rid: reasons for rid, reasons in dietary.items() if reasons}
        if not self.board.read("pantry"):
            status = "empty_pantry"
        elif ranked:
            status = "ok"
        elif dietary:
            status = "all_excluded"
        else:
            status = "no_matches"
        return BlackboardResult(status, ranked, self.board.read("unrecognized"),
                                None if status == "empty_pantry" else ExclusionSummary(len(dietary), excluded),
                                time.perf_counter() - start,
                                self.board.read("combined_shopping"), activations)
