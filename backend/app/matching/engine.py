"""MatchEngine — compare claimed application fields against the extracted label.

Pure and deterministic given (ClaimedFields, ExtractedLabel). Each field uses the
strategy its regulation demands (SPEC §4): lenient/fuzzy for names, numeric for ABV
(+ proof cross-check), allowed-set for net contents, semantic/advisory for class/type,
country-iff-imported, and STRICT for the government warning.

Works identically whether the claimed values came from a parsed COLA record (F1) or a
manual-entry form (F2). When a claimed value is absent (extract-only), the field is
reported as INFO showing what the label says, never a false PASS/FAIL.
"""

from __future__ import annotations

from app.cola.models import ClaimedFields, ProductSource
from app.extraction.schema import ExtractedField, ExtractedLabel

from . import rules
from .normalize import (
    fuzzy_equal,
    net_contents_match,
    parse_abv,
    parse_net_contents,
    parse_proof,
)
from .verdict import FieldVerdict, Status, VerificationResult
from .warning_text import check_warning


class MatchEngine:
    def verify(self, claimed: ClaimedFields, extracted: ExtractedLabel) -> VerificationResult:
        verdicts: list[FieldVerdict] = []
        verdicts.append(self._brand(claimed, extracted))
        if claimed.fanciful_name:
            verdicts.append(self._fanciful(claimed, extracted))
        verdicts.append(self._class_type(claimed, extracted))
        verdicts.extend(self._alcohol(claimed, extracted))
        verdicts.append(self._net_contents(claimed, extracted))
        verdicts.append(self._producer(claimed, extracted))
        verdicts.append(self._country(claimed, extracted))
        verdicts.append(self._warning(extracted))

        result = VerificationResult(fields=verdicts, image_quality=extracted.image_quality)
        result.compute_overall()
        self._apply_image_quality_guard(result, extracted)
        return result

    # ----- individual matchers ----------------------------------------------

    def _brand(self, claimed: ClaimedFields, ex: ExtractedLabel) -> FieldVerdict:
        candidates = _values(ex.brand_name, ex.fanciful_name)
        if not claimed.brand_name:
            return _info("brand_name", "Brand Name", None, ex.brand_name,
                         "No application brand to compare; label shows this value.")
        if any(fuzzy_equal(claimed.brand_name, c) for c in candidates):
            via = "" if fuzzy_equal(claimed.brand_name, ex.brand_name.value) else " (matched via fanciful name on label)"
            return FieldVerdict(
                field="brand_name", label="Brand Name", status=Status.PASS,
                claimed=claimed.brand_name, extracted=ex.brand_name.value,
                reason=f"Brand name matches the label{via}.",
                confidence=ex.brand_name.confidence, source_image=ex.brand_name.source_image,
            )
        if not candidates:
            return FieldVerdict(
                field="brand_name", label="Brand Name", status=Status.FAIL,
                claimed=claimed.brand_name, extracted=None,
                reason="Brand name not found on the label.",
                confidence=ex.brand_name.confidence,
            )
        return FieldVerdict(
            field="brand_name", label="Brand Name", status=Status.FAIL,
            claimed=claimed.brand_name, extracted=ex.brand_name.value,
            reason=f"Label brand '{ex.brand_name.value}' does not match application brand '{claimed.brand_name}'.",
            confidence=ex.brand_name.confidence, source_image=ex.brand_name.source_image,
        )

    def _fanciful(self, claimed: ClaimedFields, ex: ExtractedLabel) -> FieldVerdict:
        candidates = _values(ex.fanciful_name, ex.brand_name)
        if any(fuzzy_equal(claimed.fanciful_name, c) for c in candidates):
            return FieldVerdict(
                field="fanciful_name", label="Fanciful Name", status=Status.PASS,
                claimed=claimed.fanciful_name, extracted=ex.fanciful_name.value,
                reason="Fanciful name appears on the label.",
                confidence=ex.fanciful_name.confidence, source_image=ex.fanciful_name.source_image,
            )
        return FieldVerdict(
            field="fanciful_name", label="Fanciful Name", status=Status.FLAG,
            claimed=claimed.fanciful_name, extracted=ex.fanciful_name.value,
            reason=f"Application fanciful name '{claimed.fanciful_name}' not clearly found on the label.",
            confidence=ex.fanciful_name.confidence,
        )

    def _class_type(self, claimed: ClaimedFields, ex: ExtractedLabel) -> FieldVerdict:
        # Advisory: the TTB class/type code is never verbatim on the label (SPEC §4).
        if ex.class_type.present and ex.class_type.value:
            return FieldVerdict(
                field="class_type", label="Class / Type", status=Status.INFO,
                claimed=claimed.class_type_description, extracted=ex.class_type.value,
                reason="Label designation shown; TTB class/type code is advisory (codes are not printed verbatim on labels).",
                confidence=ex.class_type.confidence, source_image=ex.class_type.source_image,
            )
        return FieldVerdict(
            field="class_type", label="Class / Type", status=Status.FLAG,
            claimed=claimed.class_type_description, extracted=None,
            reason="No class/type designation clearly found on the label.",
        )

    def _alcohol(self, claimed: ClaimedFields, ex: ExtractedLabel) -> list[FieldVerdict]:
        out: list[FieldVerdict] = []
        claimed_abv = parse_abv(claimed.alcohol_content)
        label_abv = parse_abv(ex.alcohol_content.value)
        required = rules.is_required("alcohol_content", claimed.product_type, claimed.source)

        if not ex.alcohol_content.present or label_abv is None:
            status = Status.FAIL if required else Status.INFO
            reason = (
                "Alcohol content is required for this product type but was not found on the label."
                if required else "Alcohol content not stated (optional for this product type)."
            )
            out.append(FieldVerdict(field="alcohol_content", label="Alcohol Content",
                                    status=status, claimed=claimed.alcohol_content,
                                    extracted=ex.alcohol_content.value, reason=reason,
                                    confidence=ex.alcohol_content.confidence))
        elif claimed_abv is None:
            out.append(_info("alcohol_content", "Alcohol Content", None, ex.alcohol_content,
                             f"Label states {label_abv}% ABV; no application value to compare."))
        else:
            diff = abs(claimed_abv - label_abv)
            if diff <= 0.1:
                status, reason = Status.PASS, f"ABV matches ({label_abv}%)."
            elif diff <= 1.0:
                status, reason = Status.FLAG, f"Minor ABV discrepancy: application {claimed_abv}% vs label {label_abv}%."
            else:
                status, reason = Status.FAIL, f"ABV mismatch: application {claimed_abv}% vs label {label_abv}%."
            out.append(FieldVerdict(field="alcohol_content", label="Alcohol Content", status=status,
                                    claimed=claimed.alcohol_content, extracted=ex.alcohol_content.value,
                                    reason=reason, confidence=ex.alcohol_content.confidence,
                                    source_image=ex.alcohol_content.source_image))

        # Proof cross-check: proof must equal 2 x ABV (SPEC §4, F4.4).
        proof = parse_proof(ex.alcohol_content.value)
        if proof is not None and label_abv is not None:
            if abs(proof - 2 * label_abv) <= 0.2:
                out.append(FieldVerdict(field="proof_check", label="Proof / ABV consistency",
                                        status=Status.PASS, extracted=ex.alcohol_content.value,
                                        reason=f"Proof {proof:g} equals 2 × {label_abv}% ABV."))
            else:
                out.append(FieldVerdict(field="proof_check", label="Proof / ABV consistency",
                                        status=Status.FLAG, extracted=ex.alcohol_content.value,
                                        reason=f"Proof {proof:g} does not equal 2 × ABV ({2 * label_abv:g} expected)."))
        return out

    def _net_contents(self, claimed: ClaimedFields, ex: ExtractedLabel) -> FieldVerdict:
        required = rules.is_required("net_contents", claimed.product_type, claimed.source)
        if not ex.net_contents.present or not ex.net_contents.value:
            return FieldVerdict(field="net_contents", label="Net Contents",
                                status=Status.FAIL if required else Status.INFO,
                                claimed=", ".join(claimed.net_contents) or None, extracted=None,
                                reason="Net contents not found on the label.",
                                confidence=ex.net_contents.confidence)
        if not claimed.net_contents:
            return _info("net_contents", "Net Contents", None, ex.net_contents,
                         f"Label states {ex.net_contents.value}; no application value to compare.")
        if parse_net_contents(ex.net_contents.value) is None:
            return FieldVerdict(field="net_contents", label="Net Contents", status=Status.FLAG,
                                claimed=", ".join(claimed.net_contents), extracted=ex.net_contents.value,
                                reason=f"Could not interpret net contents '{ex.net_contents.value}'.",
                                confidence=ex.net_contents.confidence)
        if net_contents_match(ex.net_contents.value, claimed.net_contents):
            return FieldVerdict(field="net_contents", label="Net Contents", status=Status.PASS,
                                claimed=", ".join(claimed.net_contents), extracted=ex.net_contents.value,
                                reason="Net contents matches an approved size.",
                                confidence=ex.net_contents.confidence, source_image=ex.net_contents.source_image)
        return FieldVerdict(field="net_contents", label="Net Contents", status=Status.FAIL,
                            claimed=", ".join(claimed.net_contents), extracted=ex.net_contents.value,
                            reason=f"Label net contents '{ex.net_contents.value}' is not among approved sizes ({', '.join(claimed.net_contents)}).",
                            confidence=ex.net_contents.confidence, source_image=ex.net_contents.source_image)

    def _producer(self, claimed: ClaimedFields, ex: ExtractedLabel) -> FieldVerdict:
        candidates = [c for c in (claimed.applicant_name_address, claimed.dba_tradename) if c]
        if not ex.producer_name.present or not ex.producer_name.value:
            return FieldVerdict(field="producer_name", label="Producer / Bottler", status=Status.FLAG,
                                claimed=claimed.dba_tradename or claimed.applicant_name_address, extracted=None,
                                reason="Producer/bottler name not clearly found on the label.",
                                confidence=ex.producer_name.confidence)
        if not candidates:
            return _info("producer_name", "Producer / Bottler", None, ex.producer_name,
                         f"Label shows producer '{ex.producer_name.value}'; no application value to compare.")
        if any(fuzzy_equal(ex.producer_name.value, c) for c in candidates):
            via = " (matches approved trade name / DBA)" if (
                claimed.dba_tradename and fuzzy_equal(ex.producer_name.value, claimed.dba_tradename)
            ) else ""
            return FieldVerdict(field="producer_name", label="Producer / Bottler", status=Status.PASS,
                                claimed=claimed.dba_tradename or claimed.applicant_name_address,
                                extracted=ex.producer_name.value,
                                reason=f"Producer matches the applicant{via}.",
                                confidence=ex.producer_name.confidence, source_image=ex.producer_name.source_image)
        return FieldVerdict(field="producer_name", label="Producer / Bottler", status=Status.FLAG,
                            claimed=claimed.dba_tradename or claimed.applicant_name_address,
                            extracted=ex.producer_name.value,
                            reason=f"Label producer '{ex.producer_name.value}' did not clearly match the applicant or approved DBA.",
                            confidence=ex.producer_name.confidence, source_image=ex.producer_name.source_image)

    def _country(self, claimed: ClaimedFields, ex: ExtractedLabel) -> FieldVerdict:
        if claimed.source == ProductSource.IMPORTED:
            if ex.country_of_origin.present and ex.country_of_origin.value:
                return FieldVerdict(field="country_of_origin", label="Country of Origin", status=Status.PASS,
                                    extracted=ex.country_of_origin.value,
                                    reason="Imported product states country of origin.",
                                    confidence=ex.country_of_origin.confidence,
                                    source_image=ex.country_of_origin.source_image)
            return FieldVerdict(field="country_of_origin", label="Country of Origin", status=Status.FAIL,
                                extracted=None,
                                reason="Imported product must state a country of origin; none found on the label.",
                                confidence=ex.country_of_origin.confidence)
        if claimed.source == ProductSource.DOMESTIC:
            return FieldVerdict(field="country_of_origin", label="Country of Origin", status=Status.INFO,
                                extracted=ex.country_of_origin.value,
                                reason="Domestic product — country of origin not required.")
        return FieldVerdict(field="country_of_origin", label="Country of Origin", status=Status.NOT_CHECKED,
                            extracted=ex.country_of_origin.value,
                            reason="Product source not determined; country-of-origin requirement not assessed.")

    def _warning(self, ex: ExtractedLabel) -> FieldVerdict:
        wc = check_warning(
            ex.government_warning.value,
            present=ex.government_warning.present,
            prefix_all_caps=ex.warning_prefix_all_caps,
        )
        bold_note = ""
        if ex.warning_appears_bold is False:
            bold_note = " (advisory: prefix may not be bold — outside COLA certification scope)"

        if not wc.present:
            return _warn_verdict(Status.FAIL, ex, "Government warning statement not found on the label.")
        if not wc.content_ok:
            missing = ", ".join(wc.missing_clauses) or "wording differs from the required statement"
            return _warn_verdict(Status.FAIL, ex, f"Government warning wording is non-compliant; missing/altered: {missing}.")
        if wc.prefix_all_caps is False:
            return _warn_verdict(Status.FAIL, ex, "'GOVERNMENT WARNING:' must appear in capital letters; it does not.")
        return _warn_verdict(Status.PASS, ex, f"Government warning present and matches the required statement{bold_note}.")

    def _apply_image_quality_guard(self, result: VerificationResult, ex: ExtractedLabel) -> None:
        """Low image quality must never read as a confident PASS (SPEC F6, TC-13)."""
        if ex.image_quality == "low":
            result.notes = "Image quality is low — consider requesting a clearer image before relying on this result."
            if result.overall == Status.PASS:
                result.overall = Status.FLAG


# ----- small helpers --------------------------------------------------------

def _values(*fields: ExtractedField) -> list[str]:
    return [f.value for f in fields if f.present and f.value]


def _info(field: str, label: str, claimed: str | None, ex_field: ExtractedField, reason: str) -> FieldVerdict:
    return FieldVerdict(field=field, label=label, status=Status.INFO, claimed=claimed,
                        extracted=ex_field.value, reason=reason, confidence=ex_field.confidence,
                        source_image=ex_field.source_image)


def _warn_verdict(status: Status, ex: ExtractedLabel, reason: str) -> FieldVerdict:
    return FieldVerdict(field="government_warning", label="Government Warning", status=status,
                        claimed="(mandatory 27 CFR §16.21 statement)", extracted=ex.government_warning.value,
                        reason=reason, confidence=ex.government_warning.confidence,
                        source_image=ex.government_warning.source_image)
