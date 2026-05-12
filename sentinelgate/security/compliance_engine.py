from __future__ import annotations
import re
import yaml
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional


@dataclass
class Rule:
    id: str
    name: str
    pattern: str
    case_sensitive: bool = False
    metadata: dict = None


@dataclass
class CompliancePack:
    name: str
    framework: str
    rule_count: int
    rules: List[Rule]


def _load_policy_file(path: Path) -> Optional[CompliancePack]:
    # Try a robust, tolerant parse that handles raw YAML with regex-heavy patterns
    txt = path.read_text(encoding='utf-8')

    # framework
    fw = None
    m = re.search(r'framework:\s*"?([^"\n]+)"?', txt)
    if m:
        fw = m.group(1).strip()

    # policy name
    name = None
    m2 = re.search(r'name:\s*"([^"]+)"', txt)
    if m2:
        name = m2.group(1)
    else:
        name = path.stem

    rules = []
    # Find rule blocks by locating '- id:' anchors and capturing until the next '- id:'
    for match in re.finditer(r'-\s*id:\s*"([^"]+)"(.*?)(?=(?:-\s*id:)|\Z)', txt, re.S):
        rid = match.group(1)
        block = match.group(2)
        rname = None
        rpat = ""
        rcase = False
        rmeta = {}

        m_name = re.search(r'name:\s*"([^"]+)"', block)
        if m_name:
            rname = m_name.group(1)
        m_pat = re.search(r'pattern:\s*"([\s\S]*?)"', block)
        if m_pat:
            rpat = m_pat.group(1)
        m_case = re.search(r'case_sensitive:\s*(true|True|1)', block)
        if m_case:
            rcase = True
        m_hip = re.search(r'hipaa_ref:\s*"([^"]+)"', block)
        if m_hip:
            rmeta['hipaa_ref'] = m_hip.group(1)

        rules.append(Rule(id=rid, name=(rname or rid), pattern=rpat or "", case_sensitive=rcase, metadata=rmeta))

    pack = CompliancePack(name=name or path.stem, framework=fw or name or path.stem, rule_count=len(rules), rules=rules)
    return pack


def load_compliance_packs(dir_path: str | Path = "policies") -> List[CompliancePack]:
    base = Path(dir_path)
    packs: List[CompliancePack] = []
    if not base.exists():
        return packs
    for f in sorted(base.glob("*.yaml")):
        p = _load_policy_file(f)
        if p:
            packs.append(p)
    return packs


def check_compliance(text: str, packs: List[CompliancePack]):
    """Return a SimpleNamespace with matched (bool), rule_name, compliance_refs"""
    for pack in packs:
        for rule in pack.rules:
            flags = 0 if rule.case_sensitive else re.IGNORECASE
            try:
                if rule.pattern and re.search(rule.pattern, text, flags):
                    refs = []
                    if isinstance(rule.metadata, dict):
                        # collect any HIPAA / compliance refs available
                        for k, v in rule.metadata.items():
                            if isinstance(v, str) and ("HIPAA" in k.upper() or "ref" in k.lower()):
                                refs.append(v)
                        # also look for hipaa_ref specifically
                        if "hipaa_ref" in rule.metadata:
                            refs.append(rule.metadata.get("hipaa_ref"))
                    return SimpleNamespace(matched=True, rule_name=rule.name, compliance_refs=refs)
            except re.error:
                continue
    return SimpleNamespace(matched=False, rule_name=None, compliance_refs=[])
