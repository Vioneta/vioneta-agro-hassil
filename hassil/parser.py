import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

GROUP_START = "("
GROUP_END = ")"
OPT_START = "["
OPT_END = "]"
LIST_START = "{"
LIST_END = "}"
RULE_START = "<"
RULE_END = ">"

DELIM_START = {
    GROUP_START: GROUP_END,
    OPT_START: OPT_END,
    LIST_START: LIST_END,
    RULE_START: RULE_END,
}
DELIM_END = {v: k for k, v in DELIM_START.items()}

WORD_SEP = " "
ALT_SEP = "|"
ESCAPE_CHAR = "\\"


class ParseType(Enum):
    GROUP = auto()
    OPT = auto()
    ALT = auto()
    RULE = auto()
    LIST = auto()
    WORD = auto()
    END = auto()


@dataclass
class ParseChunk:
    text: str
    start_index: int
    end_index: int
    parse_type: ParseType


def find_end_delimiter(
    text: str, start_index: int, start_char: str, end_char: str
) -> Optional[int]:
    if start_index > 0:
        text = text[start_index:]

    stack = 1
    is_escaped = False
    for i, c in enumerate(text):
        if is_escaped:
            is_escaped = False
            continue

        if c == ESCAPE_CHAR:
            is_escaped = True
            continue

        if c == end_char:
            stack -= 1
            if stack < 0:
                return None

            if stack == 0:
                return start_index + i + 1

        if c == start_char:
            stack += 1

    return None


def find_end_word(text: str, start_index: int) -> Optional[int]:
    if start_index > 0:
        text = text[start_index:]

    is_escaped = False
    separator_found = False
    for i, c in enumerate(text):
        if is_escaped:
            is_escaped = False
            continue

        if c == ESCAPE_CHAR:
            is_escaped = True
            continue

        if (i > 0) and (c == WORD_SEP):
            separator_found = True
            continue

        if separator_found and (c != WORD_SEP):
            # Start of next word
            return start_index + i

        if (c == ALT_SEP) or (c in DELIM_START) or (c in DELIM_END):
            return start_index + i

    if text:
        # Entire text is a word
        return start_index + len(text)

    return None


def peek_type(text, start_index: int) -> ParseType:
    if start_index >= len(text):
        return ParseType.END

    c = text[start_index]
    if c == GROUP_START:
        return ParseType.GROUP

    if c == OPT_START:
        return ParseType.OPT

    if c == ALT_SEP:
        return ParseType.ALT

    if c == LIST_START:
        return ParseType.LIST

    if c == RULE_START:
        return ParseType.RULE

    return ParseType.WORD


class ParseError(Exception):
    pass


def skip_text(text: str, start_index: int, skip: str) -> int:
    if start_index > 0:
        text = text[start_index:]

    if not text:
        raise ParseError(text)

    text_index = 0
    for c_text in text:
        if c_text == ESCAPE_CHAR:
            text_index += 1
            continue

        if c_text != skip[0]:
            break

        text_index += 1
        skip = skip[1:]

        if not skip:
            break

    if skip:
        raise ParseError(text)

    return start_index + text_index


def next_chunk(text: str, start_index: int = 0) -> Optional[ParseChunk]:
    next_type = peek_type(text, start_index)

    if next_type == ParseType.WORD:
        # Single word
        word_end_index = find_end_word(text, start_index)
        if word_end_index is None:
            raise ParseError(text)

        word_text = remove_escapes(text[start_index:word_end_index])

        return ParseChunk(
            text=word_text,
            start_index=start_index,
            end_index=word_end_index,
            parse_type=ParseType.WORD,
        )

    if next_type == ParseType.GROUP:
        # Skip '('
        group_start_index = skip_text(text, start_index, GROUP_START)
        group_end_index = find_end_delimiter(
            text, group_start_index, GROUP_START, GROUP_END
        )
        if group_end_index is None:
            raise ParseError(text)

        group_text = remove_escapes(text[start_index:group_end_index])

        return ParseChunk(
            text=group_text,
            start_index=start_index,
            end_index=group_end_index,
            parse_type=ParseType.GROUP,
        )

    if next_type == ParseType.OPT:
        # Skip '['
        opt_start_index = skip_text(text, start_index, OPT_START)
        opt_end_index = find_end_delimiter(text, opt_start_index, OPT_START, OPT_END)
        if opt_end_index is None:
            raise ParseError(text)

        opt_text = remove_escapes(text[start_index:opt_end_index])

        return ParseChunk(
            text=opt_text,
            start_index=start_index,
            end_index=opt_end_index,
            parse_type=ParseType.OPT,
        )

    if next_type == ParseType.LIST:
        # Skip '{'
        list_start_index = skip_text(text, start_index, LIST_START)
        list_end_index = find_end_delimiter(
            text, list_start_index, LIST_START, LIST_END
        )
        if list_end_index is None:
            raise ParseError(text)

        return ParseChunk(
            text=remove_escapes(text[start_index:list_end_index]),
            start_index=start_index,
            end_index=list_end_index,
            parse_type=ParseType.LIST,
        )

    if next_type == ParseType.RULE:
        # Skip '<'
        rule_start_index = skip_text(text, start_index, RULE_START)
        rule_end_index = find_end_delimiter(
            text, rule_start_index, RULE_START, RULE_END
        )
        if rule_end_index is None:
            raise ParseError(text)

        return ParseChunk(
            text=remove_escapes(text[start_index:rule_end_index]),
            start_index=start_index,
            end_index=rule_end_index,
            parse_type=ParseType.RULE,
        )

    if next_type == ParseType.ALT:
        return ParseChunk(
            text=text[start_index : start_index + 1],
            start_index=start_index,
            end_index=start_index + 1,
            parse_type=ParseType.ALT,
        )

    return None


def remove_delimiters(
    text: str, start_char: str, end_char: Optional[str] = None
) -> str:
    if end_char is None:
        assert len(text) > 1, "Text is too short"
        assert text[0] == start_char, "Wrong start char"
        return text[1:]

    assert len(text) > 2, "Text is too short"
    assert text[0] == start_char, "Wrong start char"
    assert text[-1] == end_char, "Wrong end char"
    return text[1:-1]


def remove_escapes(text: str) -> str:
    """Remove backslash escape sequences"""
    return re.sub(r"\\(.)", r"\1", text)


def escape_text(text: str) -> str:
    """Escape parentheses, etc."""
    return re.sub(r"([()\[\]{}<>])", r"\\\1", text)
