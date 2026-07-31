/* =========================================================
   백엔드 API 클라이언트
   실제 URL/헤더는 이 파일에서만 다루고, 화면 코드는
   window.CourseApi 어댑터를 통해서만 데이터를 요청한다.
   ========================================================= */
(function (global) {
  "use strict";

  // API 기본 주소는 한 곳에서만 관리한다.
  // 다른 환경에서는 페이지에서 window.__API_BASE_URL__ 를 미리 지정할 수 있다.
  var API_BASE_URL =
    (global.__API_BASE_URL__ || "http://127.0.0.1:8000").replace(/\/+$/, "");

  async function apiRequest(path, options) {
    options = options || {};
    var res = await fetch(API_BASE_URL + path, Object.assign(
      { headers: { "Content-Type": "application/json" } },
      options
    ));

    var body = null;
    try {
      body = await res.json();
    } catch (_) {
      /* 본문이 없거나 JSON 이 아님 */
    }

    if (!res.ok) {
      var err = new Error("API 요청 실패");
      err.status = res.status;
      err.body = body;
      throw err;
    }
    return body;
  }

  // 서버/네트워크 오류를 사용자에게 보여줄 문구로 변환한다.
  function messageFromError(err) {
    if (!err || err.status === undefined) {
      return "서버에 연결할 수 없어요. 백엔드가 실행 중인지 확인한 뒤 다시 시도해 주세요.";
    }
    if (err.body && err.body.error && err.body.error.message) {
      return err.body.error.message; // 예측된 업무 오류
    }
    if (err.body && Array.isArray(err.body.detail) && err.body.detail[0]) {
      return err.body.detail[0].msg || "입력값을 다시 확인해 주세요.";
    }
    return "요청에 실패했어요. (HTTP " + err.status + ")";
  }

  // 오류에 담긴 업무 오류 코드(없으면 null). 화면에서 분기용으로 사용한다.
  function codeFromError(err) {
    if (err && err.body && err.body.error && err.body.error.code) {
      return err.body.error.code;
    }
    return null;
  }

  // 객체를 안전한 쿼리스트링으로 변환한다(빈 값은 생략).
  function toQuery(params) {
    if (!params) return "";
    var parts = [];
    Object.keys(params).forEach(function (key) {
      var value = params[key];
      if (value === undefined || value === null || value === "") return;
      parts.push(encodeURIComponent(key) + "=" + encodeURIComponent(value));
    });
    return parts.length ? "?" + parts.join("&") : "";
  }

  // 경로 조각 헬퍼: 아카데미/수강생 하위 경로를 반복해서 쓰지 않는다.
  function academyPath(academyId, suffix) {
    return "/api/academies/" + academyId + (suffix || "");
  }

  function studentPath(academyId, studentId, suffix) {
    return academyPath(academyId, "/students/" + studentId + (suffix || ""));
  }

  function send(path, method, payload) {
    return apiRequest(path, {
      method: method,
      body: JSON.stringify(payload || {}),
    });
  }

  var academies = {
    // 아카데미 목록 조회 → { items, pagination }
    list: function (params) {
      return apiRequest("/api/academies" + toQuery(params));
    },
    // 아카데미 생성 → 생성된 아카데미 객체 반환
    create: function (payload) {
      return send("/api/academies", "POST", payload);
    },
    // 아카데미 상세 조회
    get: function (academyId) {
      return apiRequest(academyPath(academyId));
    },
    // 아카데미 수정(부분 수정)
    update: function (academyId, payload) {
      return send(academyPath(academyId), "PATCH", payload);
    },
    // 아카데미 삭제 → 본문 없음(204)
    remove: function (academyId) {
      return apiRequest(academyPath(academyId), { method: "DELETE" });
    },
    // 아카데미 요약(회원·수강권·오늘 수강 집계)
    summary: function (academyId) {
      return apiRequest(academyPath(academyId, "/summary"));
    },
  };

  var passTypes = {
    // 특정 아카데미의 수강권 종류 목록 조회 → { items, pagination }
    list: function (academyId, params) {
      return apiRequest(academyPath(academyId, "/pass-types") + toQuery(params));
    },
    // 수강권 종류 생성 → 생성된 수강권 종류 객체 반환
    create: function (academyId, payload) {
      return send(academyPath(academyId, "/pass-types"), "POST", payload);
    },
    // 수강권 종류 상세 조회
    get: function (academyId, passTypeId) {
      return apiRequest(academyPath(academyId, "/pass-types/" + passTypeId));
    },
    // 수강권 종류 수정 → 수정된 수강권 종류 객체 반환
    update: function (academyId, passTypeId, payload) {
      return send(
        academyPath(academyId, "/pass-types/" + passTypeId),
        "PATCH",
        payload
      );
    },
    // 수강권 종류 삭제 → 본문 없음(204)
    remove: function (academyId, passTypeId) {
      return apiRequest(academyPath(academyId, "/pass-types/" + passTypeId), {
        method: "DELETE",
      });
    },
  };

  var students = {
    // 특정 아카데미의 수강생 목록 조회 → { items, pagination }
    list: function (academyId, params) {
      return apiRequest(academyPath(academyId, "/students") + toQuery(params));
    },
    // 수강생 생성 → 생성된 수강생 객체 반환
    create: function (academyId, payload) {
      return send(academyPath(academyId, "/students"), "POST", payload);
    },
    // 수강생 상세 조회
    get: function (academyId, studentId) {
      return apiRequest(studentPath(academyId, studentId));
    },
    // 수강생 수정(이름·전화·이메일·메모)
    update: function (academyId, studentId, payload) {
      return send(studentPath(academyId, studentId), "PATCH", payload);
    },
    // 수강생 삭제 → 본문 없음(204)
    remove: function (academyId, studentId) {
      return apiRequest(studentPath(academyId, studentId), {
        method: "DELETE",
      });
    },
    // 수강생 요약(보유 수강권·수강 기록 집계)
    summary: function (academyId, studentId) {
      return apiRequest(studentPath(academyId, studentId, "/summary"));
    },
    // 사용 가능한 보유 수강권 배열(잔여 1회 이상 + 만료 전)
    availablePasses: function (academyId, studentId) {
      return apiRequest(
        studentPath(academyId, studentId, "/available-passes")
      );
    },
    // 수강생 전체 수강 기록 → { items, pagination }
    attendanceRecords: function (academyId, studentId, params) {
      return apiRequest(
        studentPath(academyId, studentId, "/attendance-records") +
          toQuery(params)
      );
    },
    // 회원 포털 홈 요약(수강권·오늘 일정·다음 예약·문의 건수)
    portalSummary: function (academyId, studentId) {
      return apiRequest(studentPath(academyId, studentId, "/portal-summary"));
    },
  };

  // 회원 예약 목록(수강권 잔여 횟수 포함).
  var reservations = {
    list: function (academyId, studentId, query) {
      return apiRequest(
        studentPath(academyId, studentId, "/reservations") + toQuery(query)
      );
    },
  };

  var studentPasses = {
    // 보유 수강권 목록 → { items, pagination }
    list: function (academyId, studentId, params) {
      return apiRequest(
        studentPath(academyId, studentId, "/passes") + toQuery(params)
      );
    },
    // 수강권 발급(발급 + 회원 만료일 갱신이 한 트랜잭션)
    create: function (academyId, studentId, payload) {
      return send(studentPath(academyId, studentId, "/passes"), "POST", payload);
    },
    // 보유 수강권 상세 조회
    get: function (academyId, studentId, studentPassId) {
      return apiRequest(
        studentPath(academyId, studentId, "/passes/" + studentPassId)
      );
    },
    // 보유 수강권 수정(시작일·만료일)
    update: function (academyId, studentId, studentPassId, payload) {
      return send(
        studentPath(academyId, studentId, "/passes/" + studentPassId),
        "PATCH",
        payload
      );
    },
    // 보유 수강권 삭제 → 본문 없음(204)
    remove: function (academyId, studentId, studentPassId) {
      return apiRequest(
        studentPath(academyId, studentId, "/passes/" + studentPassId),
        { method: "DELETE" }
      );
    },
    // 보유 수강권별 수강 기록 → { items, pagination }
    attendanceRecords: function (academyId, studentId, studentPassId, params) {
      return apiRequest(
        studentPath(
          academyId,
          studentId,
          "/passes/" + studentPassId + "/attendance-records"
        ) + toQuery(params)
      );
    },
  };

  var attendanceRecords = {
    // 수강 기록 목록 → { items, pagination }
    list: function (academyId, params) {
      return apiRequest(
        academyPath(academyId, "/attendance-records") + toQuery(params)
      );
    },
    // 예약 생성(예약 시점에는 잔여 횟수를 차감하지 않는다)
    create: function (academyId, payload) {
      return send(
        academyPath(academyId, "/attendance-records"),
        "POST",
        payload
      );
    },
    // 수강 기록 상세 조회
    get: function (academyId, attendanceRecordId) {
      return apiRequest(
        academyPath(academyId, "/attendance-records/" + attendanceRecordId)
      );
    },
    // 예약 내용 수정(RESERVED 상태만)
    update: function (academyId, attendanceRecordId, payload) {
      return send(
        academyPath(academyId, "/attendance-records/" + attendanceRecordId),
        "PATCH",
        payload
      );
    },
    // 수강 완료 처리 → 잔여 1회 차감
    complete: function (academyId, attendanceRecordId, payload) {
      return send(
        academyPath(
          academyId,
          "/attendance-records/" + attendanceRecordId + "/complete"
        ),
        "POST",
        payload
      );
    },
    // 예약 취소 → 잔여 횟수 변화 없음
    cancel: function (academyId, attendanceRecordId, payload) {
      return send(
        academyPath(
          academyId,
          "/attendance-records/" + attendanceRecordId + "/cancel"
        ),
        "POST",
        payload
      );
    },
    // 완료 취소 및 횟수 복구(사유 필수)
    restore: function (academyId, attendanceRecordId, payload) {
      return send(
        academyPath(
          academyId,
          "/attendance-records/" + attendanceRecordId + "/restore"
        ),
        "POST",
        payload
      );
    },
    // 출석 체크인 → 잔여 횟수는 차감하지 않음
    checkIn: function (academyId, attendanceRecordId) {
      return send(
        academyPath(
          academyId,
          "/attendance-records/" + attendanceRecordId + "/check-in"
        ),
        "POST"
      );
    },
    // 퇴실 → 수강 완료 + 잔여 1회 차감
    checkOut: function (academyId, attendanceRecordId) {
      return send(
        academyPath(
          academyId,
          "/attendance-records/" + attendanceRecordId + "/check-out"
        ),
        "POST"
      );
    },
  };

  // 문의: 회원용(수강생 경로)과 사업자용(아카데미 경로)을 함께 제공한다.
  var inquiries = {
    listForStudent: function (academyId, studentId, query) {
      return apiRequest(
        studentPath(academyId, studentId, "/inquiries") + toQuery(query)
      );
    },
    createForStudent: function (academyId, studentId, payload) {
      return send(
        studentPath(academyId, studentId, "/inquiries"),
        "POST",
        payload
      );
    },
    getForStudent: function (academyId, studentId, inquiryId) {
      return apiRequest(
        studentPath(academyId, studentId, "/inquiries/" + inquiryId)
      );
    },
    addStudentMessage: function (academyId, studentId, inquiryId, payload) {
      return send(
        studentPath(
          academyId,
          studentId,
          "/inquiries/" + inquiryId + "/messages"
        ),
        "POST",
        payload
      );
    },
    closeForStudent: function (academyId, studentId, inquiryId) {
      return send(
        studentPath(academyId, studentId, "/inquiries/" + inquiryId + "/close"),
        "POST"
      );
    },
    listForAcademy: function (academyId, query) {
      return apiRequest(academyPath(academyId, "/inquiries") + toQuery(query));
    },
    getForAcademy: function (academyId, inquiryId) {
      return apiRequest(academyPath(academyId, "/inquiries/" + inquiryId));
    },
    addAcademyMessage: function (academyId, inquiryId, payload) {
      return send(
        academyPath(academyId, "/inquiries/" + inquiryId + "/messages"),
        "POST",
        payload
      );
    },
    closeForAcademy: function (academyId, inquiryId) {
      return send(
        academyPath(academyId, "/inquiries/" + inquiryId + "/close"),
        "POST"
      );
    },
  };

  // 기간 기반 집계(조회 전용). query 는 { date_from, date_to, group_by ... }
  var analytics = {
    dashboard: function (academyId, query) {
      return apiRequest(
        academyPath(academyId, "/analytics/dashboard") + toQuery(query)
      );
    },
    registrations: function (academyId, query) {
      return apiRequest(
        academyPath(academyId, "/analytics/registrations") + toQuery(query)
      );
    },
    attendance: function (academyId, query) {
      return apiRequest(
        academyPath(academyId, "/analytics/attendance") + toQuery(query)
      );
    },
    passTypes: function (academyId, query) {
      return apiRequest(
        academyPath(academyId, "/analytics/pass-types") + toQuery(query)
      );
    },
  };

  // 운영 관리 대상 목록(조회 전용).
  var worklists = {
    pendingAttendance: function (academyId, query) {
      return apiRequest(
        academyPath(academyId, "/worklists/pending-attendance") + toQuery(query)
      );
    },
    expiringPasses: function (academyId, query) {
      return apiRequest(
        academyPath(academyId, "/worklists/expiring-passes") + toQuery(query)
      );
    },
    lowBalancePasses: function (academyId, query) {
      return apiRequest(
        academyPath(academyId, "/worklists/low-balance-passes") + toQuery(query)
      );
    },
    reregistrationCandidates: function (academyId, query) {
      return apiRequest(
        academyPath(academyId, "/worklists/reregistration-candidates") +
          toQuery(query)
      );
    },
  };

  // 장부 점검(조회 전용, 자동 수정 없음).
  var checks = {
    ledgerConsistency: function (academyId) {
      return apiRequest(academyPath(academyId, "/checks/ledger-consistency"));
    },
  };

  var health = {
    // 서버 연결 상태 확인
    ping: function () {
      return apiRequest("/ping");
    },
    // 서버 + 데이터베이스 상태 확인
    check: function () {
      return apiRequest("/api/health");
    },
  };

  global.CourseApi = {
    baseUrl: API_BASE_URL,
    messageFromError: messageFromError,
    codeFromError: codeFromError,
    academies: academies,
    passTypes: passTypes,
    students: students,
    studentPasses: studentPasses,
    reservations: reservations,
    attendanceRecords: attendanceRecords,
    inquiries: inquiries,
    analytics: analytics,
    worklists: worklists,
    checks: checks,
    health: health,
  };
})(window);
