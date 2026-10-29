import json
import os
from pathlib import Path
from typing import Literal

import streamlit as st
from openai import OpenAI
from pydantic import BaseModel


# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="이음 | AI Project Coordinator",
    page_icon="🔗",
    layout="centered"
)

BASE_DIR = Path(__file__).parent


# =========================================================
# 디자인
# =========================================================

st.markdown(
    """
    <style>

    .block-container {
        max-width: 760px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }

    div.stButton > button {
        width: 100%;
        min-height: 48px;
        border-radius: 10px;
        font-weight: 700;
    }

    [data-testid="stMetricValue"] {
        font-size: 2rem;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# JSON 불러오기
# =========================================================

def load_json(filename):

    path = BASE_DIR / filename

    if not path.exists():

        st.error(
            f"필수 파일을 찾을 수 없습니다: {filename}"
        )

        st.stop()

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


project_memory = load_json(
    "ieum_project_memory_v1.json"
)

current_records = load_json(
    "ieum_demo_raw_records_v2.json"
)


# =========================================================
# OpenAI API KEY
# =========================================================

def get_api_key():

    key = os.getenv(
        "OPENAI_API_KEY"
    )

    if key:
        return key

    try:

        key = st.secrets.get(
            "OPENAI_API_KEY"
        )

        if key:
            return key

    except Exception:
        pass

    return None


# =========================================================
# 반드시 확인할 프로젝트 업무영역
# =========================================================

REQUIRED_CATEGORIES = [
    "행사 일정",
    "숙소",
    "예산",
    "레크리에이션",
    "참가자 모집",
    "교통",
    "여행자보험",
    "조편성·방배정",
    "식사·준비물",
    "안전점검",
    "추가비용 안내"
]


# =========================================================
# AI 출력 구조
# =========================================================

class CurrentStatusItem(BaseModel):

    category: Literal[
        "행사 일정",
        "숙소",
        "예산",
        "레크리에이션",
        "참가자 모집",
        "교통",
        "여행자보험",
        "조편성·방배정",
        "식사·준비물",
        "안전점검",
        "추가비용 안내"
    ]

    state: Literal[
        "confirmed",
        "in_progress",
        "not_confirmed"
    ]

    summary: str

    evidence: str


class CheckItem(BaseModel):

    priority: Literal[
        "high",
        "medium"
    ]

    topic: str

    message: str

    basis: str


class MeetingBriefing(BaseModel):

    decide_now: list[str]

    confirm_with_owner: list[str]

    past_lessons: list[str]


class ProjectAnalysis(BaseModel):

    project_summary: str

    current_status: list[
        CurrentStatusItem
    ]

    check_items: list[
        CheckItem
    ]

    meeting: MeetingBriefing


# =========================================================
# 누락 카테고리 보정
# =========================================================

def normalize_status_items(status_items):

    status_map = {}

    for item in status_items:

        if item["category"] not in status_map:

            status_map[
                item["category"]
            ] = item


    normalized = []


    for category in REQUIRED_CATEGORIES:

        if category in status_map:

            normalized.append(
                status_map[category]
            )

        else:

            normalized.append(
                {
                    "category": category,
                    "state": "not_confirmed",
                    "summary":
                        "현재 제공된 기록만으로는 "
                        "이 업무의 진행 상태를 확인하기 어렵습니다.",

                    "evidence":
                        "현재 프로젝트 기록에서 "
                        "해당 업무의 진행 상태를 직접 확인할 수 있는 "
                        "근거가 확인되지 않았습니다."
                }
            )


    return normalized


# =========================================================
# 실제 AI 분석
# =========================================================

def analyze_project():

    api_key = get_api_key()

    if not api_key:

        raise RuntimeError(
            "OpenAI API 키가 설정되어 있지 않습니다."
        )


    client = OpenAI(
        api_key=api_key
    )


    memory_text = json.dumps(
        project_memory,
        ensure_ascii=False,
        indent=2
    )


    records_text = json.dumps(
        current_records,
        ensure_ascii=False,
        indent=2
    )


    prompt = f"""

다음은 하나의 현재 프로젝트에서
실제로 남아 있는 여러 기록과,
과거 유사 프로젝트의 조직 경험이다.


[현재 프로젝트 기록]

{records_text}


[과거 프로젝트 메모리]

{memory_text}



너는
AI Project Coordinator다.


사용자는 현재 프로젝트의 상태를
미리 정리해주지 않았다.


먼저 흩어진 현재 기록을 읽고
프로젝트가 현재 어디까지 진행되었는지
재구성하라.


그 다음 과거 프로젝트 경험을 참고하여

현재 프로젝트에서
사람이 지금 확인하거나
결정해야 할 사항을 찾아라.



=================================================
매우 중요한 현재상태 분석 규칙
=================================================


다음 11개 업무영역을
반드시 각각 독립적으로 분석해야 한다.


1. 행사 일정
2. 숙소
3. 예산
4. 레크리에이션
5. 참가자 모집
6. 교통
7. 여행자보험
8. 조편성·방배정
9. 식사·준비물
10. 안전점검
11. 추가비용 안내


11개 항목을 절대로 서로 묶지 마라.


예:

"참가자·교통·보험"

처럼 작성하면 안 된다.


반드시

참가자 모집

교통

여행자보험

을 각각 별도의 current_status 항목으로 작성한다.


current_status에는
위 11개 업무영역을
각각 정확히 한 번씩 포함한다.



=================================================
현재 상태 판정 기준
=================================================


confirmed

현재 기록에서
완료 또는 확정되었음을
명확하게 확인할 수 있는 상태.


in_progress

현재 기록에서

검토 중,
작성 중,
준비 중,
담당자 배정 후 기획 중

등 진행 과정에 있음을
확인할 수 있는 상태.


not_confirmed

과거 프로젝트에서
관련성이 있는 업무영역이지만

현재 제공된 기록만으로는
그 업무의 진행상태를
확인할 수 없는 경우.


중요:

현재 기록에 자료가 없다고 해서

"업무를 하지 않았다"

"미진행이다"

"누락됐다"

라고 단정하지 않는다.


반드시

"현재 제공된 기록에서는 확인되지 않는다"

라는 의미로 표현한다.



=================================================
현재 기록과 과거 기록 구분
=================================================


현재 프로젝트의 진행상태는
오직 현재 프로젝트 기록을 근거로 판단한다.


과거 프로젝트 기록을 보고

"작년에 했으니 올해도 진행 중일 것이다"

라고 추론하면 안 된다.


과거 프로젝트 기록은

현재 프로젝트에서
어떤 업무를 확인할 가치가 있는지,

어떤 문제가 반복될 가능성이 있는지,

어떤 경험을 참고할 수 있는지

판단할 때만 사용한다.



=================================================
확인사항 작성 기준
=================================================


current_status를 재구성한 뒤

현재 시점에서 사람이
확인하거나 결정해야 할 중요한 사항을
3~6개 제시한다.


priority가 high인 경우:

현재 확인하지 않으면

- 일정
- 예약
- 비용
- 안전
- 참가자 모집
- 운영

등에 영향을 줄 가능성이 높은 항목.


priority가 medium인 경우:

당장 큰 위험은 아니지만
향후 프로젝트 진행을 위해
확인할 가치가 있는 항목.



=================================================
basis 작성 기준
=================================================


basis에는 가능하면

현재 상태

+

관련 과거 프로젝트 경험

을 연결해서 설명한다.


예:

현재 숙소 후보 2곳을 비교 중이다.
과거 프로젝트 사후평가에서는
숙소 시설 안전 관련 의견이 있었다.

따라서 숙소 확정 전
안전점검 항목을 함께 확인할 가치가 있다.


과거 프로젝트 경험이 없다면
억지로 만들지 않는다.



=================================================
회의 브리핑 기준
=================================================


decide_now

다음 회의에서
실제로 결정할 필요가 있는 사항.


confirm_with_owner

현재 기록만으로 상태를 알 수 없어
담당자에게 확인해야 할 사항.


past_lessons

이번 프로젝트의 현재 상황과
직접 관련성이 높은
과거 프로젝트 경험.



=================================================
최종 원칙
=================================================


1.
과거 프로젝트는
현재 프로젝트의 정답이 아니다.


2.
AI는 사람의 최종 결정을
대신하지 않는다.


3.
기록에 없는 사실을
임의로 만들어내지 않는다.


4.
불확실하면
"확인 필요"라고 표현한다.


5.
현재 프로젝트와
관련성이 낮은 과거 경험은 제외한다.


6.
한국어로 작성한다.


7.
문장은 짧고 명확하게 작성한다.

"""


    response = client.responses.parse(

        model="gpt-6-luna",

        input=[
            {
                "role": "system",
                "content":
                    "너는 흩어진 프로젝트 기록을 읽고 "
                    "현재 프로젝트의 맥락을 재구성한 뒤 "
                    "과거 조직 경험과 연결하여 "
                    "사람의 판단을 지원하는 "
                    "AI Project Coordinator다."
            },

            {
                "role": "user",
                "content": prompt
            }
        ],

        text_format=ProjectAnalysis
    )


    result = response.output_parsed


    if result is None:

        raise RuntimeError(
            "AI 분석 결과를 생성하지 못했습니다."
        )


    result_dict = result.model_dump()


    result_dict["current_status"] = (
        normalize_status_items(
            result_dict["current_status"]
        )
    )


    return result_dict


# =========================================================
# SESSION STATE
# =========================================================

if "page" not in st.session_state:

    st.session_state.page = 0


if "ai_result" not in st.session_state:

    st.session_state.ai_result = None


def go(page):

    st.session_state.page = page

    st.rerun()


# =========================================================
# HEADER
# =========================================================

st.title(
    "🔗 이음"
)

st.caption(
    "AI Project Coordinator"
)

st.divider()


# =========================================================
# PAGE 0
# =========================================================

if st.session_state.page == 0:

    st.subheader(
        "흩어진 기록에서"
    )

    st.write(
        "프로젝트의 현재를 읽다"
    )


    st.write(
        """
프로젝트에는 수많은 기록이 남습니다.

하지만 기록이 쌓인다고 해서
현재 상황이 자동으로 정리되는 것은 아닙니다.

담당자는 다시 파일을 찾고,
읽고, 비교하고,
머릿속에서 상황을 조립해야 합니다.

**이음은 흩어진 프로젝트 기록을 읽고  
현재 상황을 재구성한 뒤  
과거 경험을 다음 판단과 연결합니다.**
"""
    )


    st.info(
        "체험 프로젝트 : "
        "2027 경영학과 MT 준비"
    )


    if st.button(
        "현재 프로젝트 기록 보기 →",
        type="primary",
        use_container_width=True
    ):

        go(1)


# =========================================================
# PAGE 1
# 프로젝트 기록
# =========================================================

elif st.session_state.page == 1:

    st.subheader(
        "현재 프로젝트 기록"
    )


    st.caption(
        "현재 공유 작업공간에서 "
        "수집된 기록입니다."
    )


    records = current_records.get(
        "records",
        []
    )


    st.metric(
        "확인된 기록",
        f"{len(records)}건"
    )


    for record in records:

        with st.expander(
            f"📄 {record['source']}"
        ):

            for content in record["content"]:

                st.write(
                    f"- {content}"
                )


    st.divider()


    st.write(
        """
이 자료만으로 프로젝트의 현재 상황을
한눈에 파악하려면 여러 기록을
직접 비교해야 합니다.
"""
    )


    if st.button(
        "✨ 이음으로 프로젝트 맥락 분석하기",
        type="primary",
        use_container_width=True
    ):

        try:

            with st.spinner(
                "흩어진 기록에서 "
                "현재 프로젝트의 맥락을 재구성하고 있습니다..."
            ):

                result = analyze_project()

                st.session_state.ai_result = result

                go(2)


        except Exception as e:

            st.error(
                "AI 분석을 실행하지 못했습니다."
            )

            st.code(
                str(e)
            )


    if st.button(
        "← 처음으로",
        use_container_width=True
    ):

        go(0)


# =========================================================
# PAGE 2
# 현재 상태 재구성
# =========================================================

elif st.session_state.page == 2:

    analysis = (
        st.session_state.ai_result
    )


    if not analysis:

        st.warning(
            "분석 결과가 없습니다."
        )

        if st.button(
            "기록 화면으로 돌아가기",
            use_container_width=True
        ):

            go(1)

        st.stop()


    st.subheader(
        "현재 프로젝트 파악 결과"
    )


    st.success(
        analysis.get(
            "project_summary",
            "현재 프로젝트의 맥락을 분석했습니다."
        )
    )


    status_items = analysis.get(
        "current_status",
        []
    )


    confirmed = sum(
        1
        for item in status_items
        if item["state"] == "confirmed"
    )


    progress = sum(
        1
        for item in status_items
        if item["state"] == "in_progress"
    )


    unknown = sum(
        1
        for item in status_items
        if item["state"] == "not_confirmed"
    )


    c1, c2, c3 = st.columns(3)


    with c1:

        st.metric(
            "확인됨",
            confirmed
        )


    with c2:

        st.metric(
            "진행 중",
            progress
        )


    with c3:

        st.metric(
            "확인 필요",
            unknown
        )


    st.write(
        "### 이음이 재구성한 현재 상태"
    )


    for item in status_items:


        if item["state"] == "confirmed":

            icon = "🟢"

            state_name = "확인됨"


        elif item["state"] == "in_progress":

            icon = "🟡"

            state_name = "진행 중"


        else:

            icon = "⚪"

            state_name = "현재 기록에서 확인 필요"


        st.markdown(
            f"""
#### {icon} {item['category']}

**{state_name}**

{item['summary']}
"""
        )


        with st.expander(
            "판단 근거 보기"
        ):

            st.write(
                item["evidence"]
            )


        st.divider()


    if st.button(
        "다음으로: 확인사항 보기 →",
        type="primary",
        use_container_width=True
    ):

        go(3)


    if st.button(
        "← 프로젝트 기록",
        use_container_width=True
    ):

        go(1)


# =========================================================
# PAGE 3
# 확인사항
# =========================================================

elif st.session_state.page == 3:

    analysis = (
        st.session_state.ai_result
    )


    check_items = analysis.get(
        "check_items",
        []
    )


    st.subheader(
        "지금 확인할 프로젝트 맥락"
    )


    high_count = sum(
        1
        for item in check_items
        if item["priority"] == "high"
    )


    medium_count = sum(
        1
        for item in check_items
        if item["priority"] == "medium"
    )


    c1, c2 = st.columns(2)


    with c1:

        st.metric(
            "우선 확인",
            f"{high_count}건"
        )


    with c2:

        st.metric(
            "확인 권장",
            f"{medium_count}건"
        )


    for item in check_items:


        if item["priority"] == "high":

            icon = "🔴"

            label = "우선 확인"


        else:

            icon = "🟡"

            label = "확인 권장"


        st.markdown(
            f"""
#### {icon} {item['topic']}

**{label}**

{item['message']}
"""
        )


        with st.expander(
            "왜 확인해야 하나요?"
        ):

            st.write(
                item["basis"]
            )

            st.caption(
                "과거 프로젝트 기록은 "
                "현재 프로젝트의 정답이 아니라 "
                "확인 필요성을 판단하기 위한 참고 근거입니다."
            )


        st.divider()


    if st.button(
        "회의 브리핑 만들기 →",
        type="primary",
        use_container_width=True
    ):

        go(4)


    if st.button(
        "← 현재 상태",
        use_container_width=True
    ):

        go(2)


# =========================================================
# PAGE 4
# 회의 브리핑
# =========================================================

elif st.session_state.page == 4:

    analysis = (
        st.session_state.ai_result
    )


    meeting = analysis.get(
        "meeting",
        {}
    )


    st.subheader(
        "다음 회의 브리핑"
    )


    st.caption(
        "사람이 다시 여러 파일을 찾기 전에 "
        "판단에 필요한 프로젝트 맥락을 정리했습니다."
    )


    st.write(
        "### 🔴 이번 회의에서 결정할 것"
    )


    decide_items = meeting.get(
        "decide_now",
        []
    )


    if decide_items:

        for i, item in enumerate(
            decide_items,
            1
        ):

            st.write(
                f"**{i}. {item}**"
            )

    else:

        st.write(
            "현재 바로 결정할 항목이 없습니다."
        )


    st.write(
        "### 🟡 담당자에게 확인할 것"
    )


    confirm_items = meeting.get(
        "confirm_with_owner",
        []
    )


    if confirm_items:

        for i, item in enumerate(
            confirm_items,
            1
        ):

            st.write(
                f"**{i}. {item}**"
            )

    else:

        st.write(
            "현재 별도로 확인할 항목이 없습니다."
        )


    st.write(
        "### 🔵 과거 프로젝트에서 참고할 경험"
    )


    past_items = meeting.get(
        "past_lessons",
        []
    )


    if past_items:

        for item in past_items:

            st.write(
                f"- {item}"
            )

    else:

        st.write(
            "- 현재 프로젝트와 직접 관련된 "
            "과거 경험이 없습니다."
        )


    st.divider()


    st.info(
        "AI는 결정을 대신하지 않습니다. "
        "사람이 판단하기 전에 필요한 "
        "프로젝트 맥락을 준비합니다."
    )


    if st.button(
        "🔄 새로 분석하기",
        type="primary",
        use_container_width=True
    ):

        st.session_state.ai_result = None

        go(1)


    if st.button(
        "처음부터 다시 보기",
        use_container_width=True
    ):

        st.session_state.ai_result = None

        go(0)