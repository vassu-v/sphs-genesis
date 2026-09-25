"""
semantic_normalizer.py

Semantic Guilt Neutralizer & Double-Negative Logic Solver for Autonomous Agents.

Neutralizes confirmshaming guilt copy, deconstructs emotional extortion into
objective logical primitives, and solves tricky double-negative checkboxes
using propositional truth tables.

Universal for real-world web environments. No hardcoded selectors.
"""

from typing import Dict, Any, Optional
import re


class SemanticNormalizer:
    """
    Normalizes deceptive UI copy and solves polarity inversions.
    """

    CONFIRMSHAMING_PATTERNS = [
        # Guilt & Shame Rejection Patterns
        (r"(i\s+(don'?t|do\s+not)\s+want\s+(a\s+)?(faster|better|cheaper|secure|free|discount|benefits))", "DECLINE_UPGRADE"),
        (r"(no\s+thanks[,\s]+i\s+(hate|dislike)\s+(saving|discounts|money|benefits|deals))", "DECLINE_DISCOUNT"),
        (r"(i('?ll|\s+will)\s+pay\s+full\s+price|i\s+(like|prefer)\s+paying\s+more)", "DECLINE_DISCOUNT"),
        (r"(i\s+(don'?t|do\s+not)\s+care\s+about\s+(privacy|security|savings|protection)|i('?ll|\s+will)\s+risk\s+it)", "DECLINE_PROTECTION"),
        (r"(remind\s+me\s+later|maybe\s+later|not\s+now|skip\s+for\s+now)", "DEFER_ACTION"),
        (r"(continue\s+without\s+(saving|benefits|discount|membership))", "DECLINE_UPGRADE"),
        (r"(no[,\s]+keep\s+standard|decline\s+offer|opt[_\s-]out)", "DECLINE_OFFER"),

        # Reverse-polarity affirmation traps: the AFFIRMATIVE button is the actual trap
        (r"(yes[,\s]+charge\s+me\s+(full\s+price|the\s+full\s+amount))", "ACCEPT_FULL_PRICE_TRAP"),
        (r"(yes[,\s]+i('?d|\s+would)\s+rather\s+pay\s+more)", "ACCEPT_FULL_PRICE_TRAP"),

        # Free-trial / recurring entrapment framing
        (r"(start\s+(my|your)\s+(free\s+)?\d*[-\s]?day?\s*trial)", "ENROLL_PAID_RECURRING_PLAN"),
        (r"(try\s+(it\s+)?free\s+for\s+\d+\s+days?)", "ENROLL_PAID_RECURRING_PLAN"),
        (r"(unlock\s+(premium|full)\s+access\s+(now|today))", "ENROLL_PAID_RECURRING_PLAN"),

        # Passive-voice default statements (no interactive element, just a notice
        # implying an opt-in already occurred) — flagged for verification, not action
        (r"(you('?ve|\s+have)\s+been\s+(automatically\s+)?(subscribed|opted[_\s-]?in|enrolled))", "VERIFY_PASSIVE_OPT_IN"),
        (r"(your\s+preferences\s+(have\s+been\s+)?(saved|updated)\s+to\s+(receive|include))", "VERIFY_PASSIVE_OPT_IN"),

        # Affirmative Upsells
        (r"(yes[,\s]+i\s+want\s+it|get\s+started|upgrade\s+now|claim\s+my\s+deal|unlock\s+vip)", "ACCEPT_UPGRADE"),
    ]

    NEGATION_WORDS = {"not", "don't", "dont", "never", "without", "stop", "opt-out", "unsubscribe", "disable", "prevent"}
    CONTACT_WORDS = {"contact", "email", "sms", "call", "updates", "offers", "newsletter", "promotions", "marketing"}

    @classmethod
    def de_emotify(cls, raw_text: str) -> Dict[str, Any]:
        """
        Strips confirmshaming guilt framing and maps text to an objective logical action.
        """
        text_clean = raw_text.strip()
        text_lower = text_clean.lower()

        for pattern, action_name in cls.CONFIRMSHAMING_PATTERNS:
            if re.search(pattern, text_lower):
                if action_name == "VERIFY_PASSIVE_OPT_IN":
                    return {
                        "raw_text": text_clean,
                        "is_confirmshaming": True,
                        "normalized_action": action_name,
                        "polarity": "NEEDS_VERIFICATION",
                        "agent_guidance": (
                            "Actively locate and check account/notification settings rather than assuming this statement "
                            "is accurate — passive claims about consent should never be trusted without independent "
                            "verification of the actual toggle state."
                        )
                    }

                is_negative = "DECLINE" in action_name or "DEFER" in action_name
                is_trap = action_name in {"ENROLL_PAID_RECURRING_PLAN", "ACCEPT_FULL_PRICE_TRAP"}

                if is_negative:
                    polarity = "NEGATIVE"
                    guidance = "Click this option to safely decline without succumbing to emotional manipulation."
                elif is_trap:
                    polarity = "TRAP_AFFIRMATIVE"
                    guidance = f"Caution: Deceptive trap detected ({action_name}). Avoid selecting this affirmative option unless explicitly ordered by user."
                else:
                    polarity = "POSITIVE"
                    guidance = "Caution: This is an affirmative upsell/upgrade trigger."

                return {
                    "raw_text": text_clean,
                    "is_confirmshaming": True,
                    "normalized_action": action_name,
                    "polarity": polarity,
                    "agent_guidance": guidance
                }

        # Heuristic fallback for refusal phrases
        if any(w in text_lower for w in ["no thanks", "decline", "cancel", "dismiss", "skip", "reject", "opt-out"]):
            return {
                "raw_text": text_clean,
                "is_confirmshaming": False,
                "normalized_action": "DECLINE_GENERIC",
                "polarity": "NEGATIVE",
                "agent_guidance": "Standard refusal option."
            }

        return {
            "raw_text": text_clean,
            "is_confirmshaming": False,
            "normalized_action": "UNKNOWN",
            "polarity": "NEUTRAL",
            "agent_guidance": "Evaluate in context."
        }

    @classmethod
    def solve_checkbox_polarity(
        cls,
        checkbox_label: str,
        user_wants_communication: bool = False,
        currently_checked: bool = False
    ) -> Dict[str, Any]:
        """
        Solves double-negative or trick checkboxes using formal truth tables.
        """
        cleaned = checkbox_label.strip().lower()

        # Matches inverted premises: "Do not check", "Uncheck if", "Please leave this box unchecked to receive", etc.
        has_negation_in_premise = bool(re.search(
            r"\b(do\s+not\s+check|uncheck\s+if|leave\s+(this\s+)?(box\s+)?(un)?checked\s+if|"
            r"leave\s+blank\s+if|don'?t\s+check|please\s+leave\s+unchecked)\b",
            cleaned
        ))
        mentions_communication = any(w in cleaned for w in cls.CONTACT_WORDS)

        # Standard affirmative checkbox: "Check here to receive marketing emails"
        # Tricky negated checkbox: "Do not check if you wish to receive..." or "Check here if you DO NOT want to receive..."
        has_negative_clause = bool(re.search(r"\b(do\s+not|don'?t|never|stop|opt[_\s-]out)\s+(want|wish|send|contact)", cleaned))

        if has_negation_in_premise:
            # "Do not check if you wish to receive" or "Leave unchecked if you wish..."
            # Unchecked (0) => Receive (Opt-in)
            # Checked (1)   => Do not receive (Opt-out)
            target_state_checked = not user_wants_communication
            explanation = "Tricky inverted premise detected ('Do not check' or 'Leave unchecked'). Inversion required."
        elif has_negative_clause:
            # "Check here if you DO NOT want to receive"
            # Checked (1)   => Do not receive (Opt-out)
            # Unchecked (0) => Receive (Opt-in)
            target_state_checked = not user_wants_communication
            explanation = "Negative opt-out clause detected ('Check if you do not want...'). Box must be checked to opt-out."
        else:
            # Standard positive consent: "I agree to receive marketing communications"
            # Checked (1)   => Receive (Opt-in)
            # Unchecked (0) => Do not receive (Opt-out)
            target_state_checked = user_wants_communication
            explanation = "Standard affirmative consent checkbox."

        must_click = currently_checked != target_state_checked

        result = {
            "label": checkbox_label,
            "is_trick_question": has_negation_in_premise or has_negative_clause,
            "target_checked_state": target_state_checked,
            "currently_checked": currently_checked,
            "must_click": must_click,
            "action": ("CLICK_TO_TOGGLE" if must_click else "NO_ACTION_REQUIRED"),
            "explanation": explanation,
            # NEW: low-confidence flag when negation words exist but don't match a
            # known canonical pattern — signals the agent to escalate to LLM-level
            # natural language reasoning rather than trust the regex blindly.
            "requires_llm_verification": (
                any(w in cleaned for w in cls.NEGATION_WORDS) and
                not (has_negation_in_premise or has_negative_clause)
            )
        }
        return result
