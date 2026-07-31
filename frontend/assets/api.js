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

  var academies = {
    // 아카데미 목록 조회 → { items, pagination }
    list: function (params) {
      return apiRequest("/api/academies" + toQuery(params));
    },
    // 아카데미 생성 → 생성된 아카데미 객체 반환
    create: function (payload) {
      return apiRequest("/api/academies", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
  };

  var passTypes = {
    // 특정 아카데미의 수강권 종류 목록 조회 → { items, pagination }
    list: function (academyId, params) {
      return apiRequest(
        "/api/academies/" + academyId + "/pass-types" + toQuery(params)
      );
    },
    // 수강권 종류 생성 → 생성된 수강권 종류 객체 반환
    create: function (academyId, payload) {
      return apiRequest("/api/academies/" + academyId + "/pass-types", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    // 수강권 종류 수정 → 수정된 수강권 종류 객체 반환
    update: function (academyId, passTypeId, payload) {
      return apiRequest(
        "/api/academies/" + academyId + "/pass-types/" + passTypeId,
        { method: "PATCH", body: JSON.stringify(payload) }
      );
    },
    // 수강권 종류 삭제 → 본문 없음(204)
    remove: function (academyId, passTypeId) {
      return apiRequest(
        "/api/academies/" + academyId + "/pass-types/" + passTypeId,
        { method: "DELETE" }
      );
    },
  };

  var students = {
    // 특정 아카데미의 수강생 목록 조회 → { items, pagination }
    list: function (academyId, params) {
      return apiRequest(
        "/api/academies/" + academyId + "/students" + toQuery(params)
      );
    },
    // 수강생 생성 → 생성된 수강생 객체 반환
    create: function (academyId, payload) {
      return apiRequest("/api/academies/" + academyId + "/students", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
  };

  var health = {
    // 서버 연결 상태 확인
    ping: function () {
      return apiRequest("/ping");
    },
  };

  global.CourseApi = {
    baseUrl: API_BASE_URL,
    messageFromError: messageFromError,
    academies: academies,
    passTypes: passTypes,
    students: students,
    health: health,
  };
})(window);
