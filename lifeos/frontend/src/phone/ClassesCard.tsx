// Your classes this year: teachers, grades, quizzes you've played, and what's coming up.
import React, { useEffect, useState } from "react";
import { ClassesView, phoneApi } from "./api";
import { cx } from "./kit";

export default function ClassesCard() {
  const [v, setV] = useState<ClassesView | null>(null);
  useEffect(() => {
    phoneApi.classes().then(setV).catch(() => setV(null));
  }, []);
  if (!v) return null;
  const next = v.upcoming[0];
  return (
    <>
      <div className="ph-section-t">Classes</div>
      <div className="ph-card cl-card">
        <div className="cl-top">
          <div><b>{v.gpa.toFixed(2)}</b><small>GPA</small></div>
          {next && (
            <div className="cl-next">
              <small>Next up</small>
              <b>{next.name}</b>
              <span>{next.in_days === 0 ? "today" : next.in_days === 1 ? "tomorrow" : `in ${next.in_days} days`}</span>
            </div>
          )}
        </div>
        <div className="cl-list">
          {v.classes.map((c) => (
            <div key={c.id} className="cl-row">
              <div className="cl-m">
                <b>{c.name}</b>
                <span>
                  {c.teacher}{c.quizzes ? ` · ${c.quizzes} quiz${c.quizzes === 1 ? "" : "zes"} played (${c.quiz_avg}%)` : ""}
                  {c.games ? ` · class games ${c.games_won}/${c.games}` : ""}
                </span>
              </div>
              <span className={cx("cl-grade", c.letter[0] === "A" ? "a" : c.letter[0] === "B" ? "b" : c.letter[0] === "C" ? "c" : "d")}>{c.letter}</span>
            </div>
          ))}
        </div>
        <p className="ph-dim small" style={{ margin: "10px 0 0" }}>
          On quiz and test days you can take it yourself. Your answers count toward the grade, along with how much you've studied.
          Most other days a teacher throws something quick at the class. Going for it nudges that grade a little.
        </p>
      </div>
    </>
  );
}
