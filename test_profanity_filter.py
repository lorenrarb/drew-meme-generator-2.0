#!/usr/bin/env python3
"""Test script for profanity filtering"""

from better_profanity import profanity

# Initialize profanity filter
profanity.load_censor_words()

# Custom blocked words
CUSTOM_BLOCKED_WORDS = [
    "nsfw", "porn", "nude", "naked", "rape", "gore", "kill", "murder",
    "suicide", "death", "blood", "hentai", "xxx"
]
profanity.add_censor_words(CUSTOM_BLOCKED_WORDS)

def test_profanity_filter():
    """Test various phrases to see if profanity filter works"""

    test_cases = [
        # Should PASS (clean content)
        ("Cute dog doing funny tricks", True),
        ("When you finish your homework on time", True),
        ("Me trying to cook dinner", True),
        ("This is hilarious", True),
        ("Wholesome meme about friendship", True),

        # Should FAIL (profanity/inappropriate)
        ("This is some bullshit", False),
        ("What the fuck is happening", False),
        ("Damn this is crazy", False),
        ("He's such an asshole", False),
        ("This shit is hilarious", False),
        ("NSFW content warning", False),
        ("Porn meme lol", False),
        ("Nude selfie", False),
        ("Gore warning", False),

        # Edge cases - variations and misspellings
        ("This is bull$hit", False),  # Special character variation
        ("What the fck", False),  # Missing vowel
        ("D@mn", False),  # Leetspeak
    ]

    print("=" * 70)
    print("PROFANITY FILTER TEST RESULTS")
    print("=" * 70)
    print()

    passed = 0
    failed = 0

    for text, should_pass in test_cases:
        has_profanity = profanity.contains_profanity(text)
        actual_pass = not has_profanity

        status = "✓ PASS" if actual_pass == should_pass else "✗ FAIL"

        if actual_pass == should_pass:
            passed += 1
        else:
            failed += 1

        censored = profanity.censor(text) if has_profanity else text

        print(f"{status}: {text}")
        print(f"        Expected: {'ALLOW' if should_pass else 'BLOCK'}")
        print(f"        Actual: {'ALLOW' if actual_pass else 'BLOCK'}")
        if has_profanity:
            print(f"        Censored: {censored}")
        print()

    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 70)

    return failed == 0

if __name__ == "__main__":
    success = test_profanity_filter()
    exit(0 if success else 1)
