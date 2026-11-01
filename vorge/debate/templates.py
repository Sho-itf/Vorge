"""議論の「型」(どの欄をどの順で書くか)と立場の定義。DB にも画面にも依存しない。"""

from dataclasses import dataclass

KIND_DEBATE = "debate"  # writings.kind に入れる値(作文と区別する)

STANCE_PRO = "pro"
STANCE_CON = "con"
STANCE_LABELS = {STANCE_PRO: "肯定側", STANCE_CON: "否定側"}
STANCE_HELP = (
    "「〜すべきか」「賛成か反対か」のお題では、肯定側=賛成、否定側=反対です。"
    "「AとB、どちらが良いか」のお題では、肯定側=A、否定側=B として考えます。"
)


def opposite(stance: str) -> str:
    return STANCE_CON if stance == STANCE_PRO else STANCE_PRO


@dataclass(frozen=True)
class Section:
    key: str
    label: str
    hint: str  # 何を書くか
    placeholder: str
    min_chars: int
    max_chars: int
    needs_evidence: bool = False  # 具体例・データがあると良い欄


@dataclass(frozen=True)
class Template:
    key: str
    label: str
    description: str
    sections: tuple[Section, ...]

    @property
    def min_chars(self) -> int:
        return sum(s.min_chars for s in self.sections)

    @property
    def max_chars(self) -> int:
        return sum(s.max_chars for s in self.sections)


PREP = Template(
    key="prep",
    label="基本(PREP法)",
    description="主張 → 理由 → 具体例 → 結論。短く手軽に、筋の通った意見を述べる型です。",
    sections=(
        Section("point", "主張", "自分の立場を一文ではっきり述べる",
                "例:私はリモートワークを広げるべきだと考える。", 20, 80),
        Section("reason", "理由", "なぜそう言えるのかを説明する(「なぜなら〜からだ」)",
                "例:なぜなら、通勤の負担が減り、働く時間を有効に使えるからだ。", 40, 150),
        Section("example", "具体例", "理由を裏付ける例・経験・データを挙げる",
                "例:実際に私の職場では、在宅勤務の導入後…", 40, 150, needs_evidence=True),
        Section("conclusion", "結論", "主張をもう一度、まとめとして述べる",
                "例:したがって、リモートワークはもっと広げるべきだ。", 20, 80),
    ),
)

REBUTTAL = Template(
    key="rebuttal",
    label="反論つき",
    description="主張 → 根拠2つ → 予想される反論 → 再反論 → 結論。反対意見に答えることで説得力を高める型です。",
    sections=(
        Section("claim", "主張", "自分の立場を一文ではっきり述べる",
                "例:私はリモートワークに賛成だ。", 20, 80),
        Section("reason1", "根拠1", "主張を支える理由と、その具体例",
                "例:第一に、通勤時間がなくなる。例えば往復2時間かかる人なら…", 40, 150,
                needs_evidence=True),
        Section("reason2", "根拠2", "根拠1とは別の観点からの理由と具体例",
                "例:第二に、育児や介護と仕事を両立しやすくなる。実際に…", 40, 150,
                needs_evidence=True),
        Section("counter", "予想される反論", "反対の立場の人が言いそうな、もっとも強い意見",
                "例:確かに、対面でないと雑談が減り、連携が弱まるという意見もある。", 30, 120),
        Section("rebuttal", "再反論", "その反論に対して、どう答えるか",
                "例:しかし、週に一度の出社日を設ければ、その問題は補える。", 40, 150),
        Section("conclusion", "結論", "根拠と再反論を踏まえて、主張をまとめる",
                "例:したがって、リモートワークは広げるべきだ。", 20, 80),
    ),
)

TEMPLATES = {t.key: t for t in (PREP, REBUTTAL)}
