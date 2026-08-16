"""Deterministic, bounded temporal pair planning inside one pose bin."""
from __future__ import annotations
from typing import Any

def plan_pairs(records:list[Any], *, rolling_step:int=5, max_long_gap:int=24):
    rs=sorted(records,key=lambda r:(r.date or "9999",r.sequence,r.record_id))
    planned=[]; seen=set()
    def add(kind,a,b):
        key=(a.record_id,b.record_id)
        if a is b or key in seen:return
        seen.add(key);planned.append((kind,a,b))
    for a,b in zip(rs,rs[1:],strict=False):add("adjacent",a,b)
    if rs:
        for b in rs[2:]:add("baseline",rs[0],b)
    for anchor in range(rolling_step,len(rs),rolling_step):
        for j in range(anchor+2,min(len(rs),anchor+max_long_gap+1),rolling_step):
            add("rolling_anchor",rs[anchor],rs[j])
    return planned
