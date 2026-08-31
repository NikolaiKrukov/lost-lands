"""Flag。命名：命名空间:实体:名称。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FlagState:
    nation_flags: dict[str, set[str]] = field(default_factory=dict)
    global_flags: set[str] = field(default_factory=set)

    def has_flag(self, nation_id: str | None, flag: str) -> bool:
        if nation_id is None:
            return flag in self.global_flags
        return flag in self.nation_flags.get(nation_id, set())

    def set_flag(self, nation_id: str | None, flag: str) -> None:
        if nation_id is None:
            self.global_flags.add(flag)
        else:
            self.nation_flags.setdefault(nation_id, set()).add(flag)

    def clr_flag(self, nation_id: str | None, flag: str) -> None:
        if nation_id is None:
            self.global_flags.discard(flag)
        else:
            self.nation_flags.get(nation_id, set()).discard(flag)

    def to_dict(self) -> dict:
        return {
            "nation_flags": {k: sorted(v) for k, v in self.nation_flags.items()},
            "global_flags": sorted(self.global_flags),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FlagState":
        fs = cls()
        for k, v in (data.get("nation_flags") or {}).items():
            fs.nation_flags[k] = set(v)
        fs.global_flags = set(data.get("global_flags") or [])
        return fs
