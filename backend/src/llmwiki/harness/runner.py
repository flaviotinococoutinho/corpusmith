from __future__ import annotations
from pathlib import Path
from .findings import Finding, Findings
from . import okf_conformance, local_policy
from ..okf.document import OKFDocument, MissingFrontmatter

class HarnessRejection(Exception):
    def __init__(self, findings: Findings):
        self.findings = findings
        errs = list(findings.errors())
        super().__init__(f"{len(errs)} erro(s): " +
                         "; ".join(f"{f.rule}@{f.path}" for f in errs[:5]))

class HarnessRunner:
    def __init__(self, reader, git):
        self.reader, self.git = reader, git

    def run(self, docs: list[OKFDocument], mode: str = "write") -> Findings:
        """Gate de escrita: docs já parseados (o writer só recebe objetos)."""
        return Findings(okf_conformance.check(docs, self.reader)) \
            .extend(local_policy.check(docs, self.reader, self.git, mode=mode))

    def lint_bundle(self, bundle_root: Path, mode: str = "write") -> Findings:
        """Auditoria do bundle inteiro: varre ARQUIVOS CRUS — malformados
        viram Finding de conformidade, nunca são engolidos em silêncio."""
        findings = Findings()
        docs: list[OKFDocument] = []
        for rel in self.reader.raw_md_files():
            text = (bundle_root / rel).read_text(errors="ignore")
            try:
                docs.append(OKFDocument.loads(rel, text))
            except MissingFrontmatter as e:
                findings.add(Finding("error", "okf.frontmatter_missing",
                                     rel, str(e), okf_conformance=True))
            except Exception as e:
                findings.add(Finding("error", "okf.frontmatter_invalid",
                                     rel, f"{type(e).__name__}: {e}",
                                     okf_conformance=True))
        findings.extend(okf_conformance.check(docs, self.reader))
        findings.extend(okf_conformance.check_reserved_files(bundle_root))
        findings.extend(local_policy.check(docs, self.reader, self.git, mode=mode))
        findings.extend(local_policy.check_corpus(docs, self.reader))
        return findings

    @staticmethod
    def has_errors(findings) -> bool:
        return any(f.severity == "error" for f in findings)
