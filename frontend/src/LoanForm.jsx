// frontend/src/LoanForm.jsx
// 심사 입력 폼: 금액은 만원 단위로 입력받아 원으로 변환해 전송
import React, { useState } from 'react';
import axios from 'axios';

const MANWON = 10000;

// key: 백엔드 loan_calculator 입력 이름 / unit: 'manwon'이면 원 ↔ 만원 변환
const FIELDS = {
  loan_amount: { label: '대출 신청 금액', unit: 'manwon', suffix: '만원' },
  annual_income: { label: '연소득', unit: 'manwon', suffix: '만원', customer: true },
  credit_score: { label: '신용점수', suffix: '점', customer: true },
  current_annual_repayment: { label: '기존 대출 연 상환액', unit: 'manwon', suffix: '만원', customer: true },
  interest_rate: { label: '금리', suffix: '%', step: '0.1' },
  term_years: { label: '대출 기간', suffix: '년' },
  stress_rate_increase: { label: '금리 상승폭', suffix: '%p', step: '0.1' },
  auto_transfers: { label: '자동이체', suffix: '건', customer: true },
  asset_amount: { label: '보유 자산', unit: 'manwon', suffix: '만원', customer: true },
  collateral_value: { label: '담보 주택 가액', unit: 'manwon', suffix: '만원' },
};

const PRODUCTS = [
  ['credit', '직장인 신용대출'],
  ['mortgage', '주택담보대출'],
  ['auto', '자동차담보대출'],
  ['policy', '새희망홀씨'],
];
const REGIONS = [['', '선택'], ['speculative', '투기과열지구'], ['adjusted', '조정대상지역'], ['normal', '기타 일반지역']];
const ROLES = [['staff', '행원'], ['manager', '지점장'], ['hq', '본부심사역']];
const TRI_STATE = [['', '모름'], ['true', '있음'], ['false', '없음']];

// 서버 값(원, bool) → 폼 값(만원, 문자열)
function toFormValues(values) {
  const form = {};
  Object.entries(values || {}).forEach(([key, value]) => {
    if (value === null || value === undefined) return;
    if (FIELDS[key]?.unit === 'manwon') form[key] = String(Math.round(value / MANWON));
    else if (typeof value === 'boolean') form[key] = String(value);
    else form[key] = String(value);
  });
  return form;
}

// 폼 값 → 서버 값. 빈칸은 보내지 않음 (백엔드가 DB 값 또는 기본값 적용)
function toPayload(form) {
  const payload = {};
  Object.entries(form).forEach(([key, value]) => {
    if (value === '' || value === undefined) return;
    if (['customer_id', 'product_type', 'region', 'user_role'].includes(key)) payload[key] = value.trim();
    else if (['has_payroll', 'is_actual_demand'].includes(key)) payload[key] = value === 'true';
    else if (FIELDS[key]?.unit === 'manwon') payload[key] = Math.round(Number(value) * MANWON);
    else if (['interest_rate', 'stress_rate_increase'].includes(key)) payload[key] = Number(value);
    else payload[key] = Math.round(Number(value));
  });
  if (payload.product_type !== 'mortgage') {
    delete payload.collateral_value;
    delete payload.region;
    delete payload.is_actual_demand;
  }
  return payload;
}

function validate(form) {
  const errors = {};
  const hasCustomer = Boolean(form.customer_id?.trim());
  const required = ['loan_amount'];
  if (!hasCustomer) required.push('annual_income', 'credit_score', 'current_annual_repayment');
  if (form.product_type === 'mortgage') required.push('collateral_value', 'region');
  required.forEach((key) => {
    if (!form[key]) errors[key] = '필수 입력입니다.';
  });
  if (!hasCustomer && !form.job_years && !form.job_months) errors.job_tenure = '필수 입력입니다.';

  Object.keys(FIELDS).concat(['job_years', 'job_months']).forEach((key) => {
    if (form[key] && (Number.isNaN(Number(form[key])) || Number(form[key]) < 0)) errors[key] = '0 이상의 숫자를 입력하세요.';
  });
  if (form.credit_score && Number(form.credit_score) > 1000) errors.credit_score = '0~1000 사이로 입력하세요.';
  if (form.interest_rate && Number(form.interest_rate) > 30) errors.interest_rate = '30% 이하로 입력하세요.';
  if (form.loan_amount && Number(form.loan_amount) === 0) errors.loan_amount = '0보다 커야 합니다.';
  return errors;
}

function summarize(payload) {
  const product = Object.fromEntries(PRODUCTS)[payload.product_type] || '직장인 신용대출';
  const parts = [];
  if (payload.customer_id) parts.push(`고객 ${payload.customer_id}`);
  parts.push(`${product} ${(payload.loan_amount / MANWON).toLocaleString()}만원`);
  if (payload.annual_income !== undefined) parts.push(`연소득 ${(payload.annual_income / MANWON).toLocaleString()}만원`);
  if (payload.credit_score !== undefined) parts.push(`신용 ${payload.credit_score}점`);
  if (payload.interest_rate !== undefined) parts.push(`금리 ${payload.interest_rate}%`);
  if (payload.term_years !== undefined) parts.push(`${payload.term_years}년`);
  if (payload.collateral_value !== undefined) parts.push(`담보 ${(payload.collateral_value / MANWON).toLocaleString()}만원`);
  return `📝 입력 폼으로 심사 요청: ${parts.join(', ')}`;
}

function LoanForm({ apiBase, form: spec, disabled, onSubmit }) {
  const [form, setForm] = useState(() => ({ product_type: 'credit', user_role: 'manager', ...toFormValues(spec?.prefilled) }));
  const [errors, setErrors] = useState({});
  const [lookupMessage, setLookupMessage] = useState('');
  const [loaded, setLoaded] = useState({}); // 불러온 고객 값 (그대로면 전송하지 않고 DB 원래 값 사용)
  const highlighted = new Set(spec?.missing || []);

  const set = (key) => (e) => setForm((prev) => ({ ...prev, [key]: e.target.value }));

  const loadCustomer = async () => {
    const id = form.customer_id?.trim();
    if (!id) {
      setLookupMessage('고객 ID를 입력하세요.');
      return;
    }
    try {
      const { data } = await axios.get(`${apiBase}/customers/${encodeURIComponent(id)}`);
      const values = {
        ...toFormValues({
          annual_income: data.annual_income,
          credit_score: data.credit_score,
          current_annual_repayment: data.current_annual_repayment,
          has_payroll: data.has_payroll,
          auto_transfers: data.auto_transfers,
          asset_amount: data.asset_amount,
        }),
        job_years: String(Math.floor(data.job_months / 12)),
        job_months: String(data.job_months % 12),
      };
      setLoaded({ ...values, customer_id: data.customer_id });
      setForm((prev) => ({ ...prev, customer_id: data.customer_id, ...values }));
      const delinquency = data.unresolved_delinquency?.count ? ` · 미해결 연체 ${data.unresolved_delinquency.count}건` : '';
      setLookupMessage(`✅ ${data.name} 고객 정보를 불러왔습니다${delinquency}`);
    } catch (error) {
      setLookupMessage(`⚠️ ${error.response?.data?.detail || '고객 정보를 불러오지 못했습니다.'}`);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const found = validate(form);
    setErrors(found);
    if (Object.keys(found).length === 0) {
      // 같은 고객의 불러온 값을 고치지 않았으면 빼고 보냄 → 백엔드가 DB 원래 값(원 단위)으로 계산
      const sameCustomer = loaded.customer_id && loaded.customer_id === form.customer_id?.trim();
      const changed = Object.fromEntries(Object.entries(form).filter(
        ([key, value]) => !(sameCustomer && key !== 'customer_id' && key in loaded && loaded[key] === value)
      ));
      const tenureChanged = 'job_years' in changed || 'job_months' in changed;
      if (tenureChanged) {
        changed.job_years = form.job_years;
        changed.job_months = form.job_months;
      }
      const payload = toPayload(changed);
      onSubmit(payload, summarize(payload));
    }
  };

  const numberField = (key) => {
    const field = FIELDS[key];
    const error = errors[key];
    return (
      <label key={key} className={`form-field${highlighted.has(key) ? ' missing' : ''}`}>
        <span>{field.label}</span>
        <div className="input-with-suffix">
          <input type="number" min="0" step={field.step || '1'} value={form[key] || ''} onChange={set(key)} disabled={disabled} />
          <em>{field.suffix}</em>
        </div>
        {error && <small className="form-error">{error}</small>}
      </label>
    );
  };

  const selectField = (key, label, options) => (
    <label key={key} className={`form-field${highlighted.has(key) ? ' missing' : ''}`}>
      <span>{label}</span>
      <select value={form[key] || ''} onChange={set(key)} disabled={disabled}>
        {options.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
      </select>
      {errors[key] && <small className="form-error">{errors[key]}</small>}
    </label>
  );

  return (
    <form className={`loan-form${disabled ? ' submitted' : ''}`} onSubmit={handleSubmit}>
      <div className="form-section">
        <h4>고객</h4>
        <div className="customer-row">
          <input placeholder="고객 ID (예: C2025_001)" value={form.customer_id || ''} onChange={set('customer_id')} disabled={disabled} />
          <button type="button" onClick={loadCustomer} disabled={disabled}>불러오기</button>
        </div>
        {lookupMessage && <small className="lookup-message">{lookupMessage}</small>}
      </div>

      <div className="form-section">
        <h4>대출 신청</h4>
        <div className="form-grid">
          {selectField('product_type', '상품 종류', PRODUCTS)}
          {numberField('loan_amount')}
          {numberField('interest_rate')}
          {numberField('term_years')}
          {selectField('user_role', '내 직급', ROLES)}
        </div>
      </div>

      {form.product_type === 'mortgage' && (
        <div className="form-section">
          <h4>담보 주택</h4>
          <div className="form-grid">
            {numberField('collateral_value')}
            {selectField('region', '지역 구분', REGIONS)}
            {selectField('is_actual_demand', '실수요자', TRI_STATE)}
          </div>
        </div>
      )}

      <div className="form-section">
        <h4>고객 정보 {form.customer_id?.trim() && <small>(비우면 고객 DB 값 사용)</small>}</h4>
        <div className="form-grid">
          {numberField('annual_income')}
          {numberField('credit_score')}
          {numberField('current_annual_repayment')}
          <label className={`form-field${highlighted.has('job_tenure') ? ' missing' : ''}`}>
            <span>재직 기간</span>
            <div className="input-with-suffix tenure">
              <input type="number" min="0" value={form.job_years || ''} onChange={set('job_years')} disabled={disabled} />
              <em>년</em>
              <input type="number" min="0" value={form.job_months || ''} onChange={set('job_months')} disabled={disabled} />
              <em>개월</em>
            </div>
            {errors.job_tenure && <small className="form-error">{errors.job_tenure}</small>}
          </label>
          {selectField('has_payroll', '급여이체', TRI_STATE)}
          {numberField('auto_transfers')}
          {numberField('asset_amount')}
          {numberField('stress_rate_increase')}
        </div>
      </div>

      <div className="form-actions">
        <small>빈칸은 기본값(금리 5%, 5년, 금리 상승폭 +2%p 등)으로 계산하고 답변에 안내합니다.</small>
        <button type="submit" disabled={disabled}>{disabled ? '제출 완료' : '심사하기'}</button>
      </div>
    </form>
  );
}

export default LoanForm;
