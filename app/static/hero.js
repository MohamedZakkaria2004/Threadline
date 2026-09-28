'use strict';

// Public, illustrative examples only. This walkthrough never invokes a model,
// reads workspace data, or performs a real action.
(() => {
  const scenes = {
    answer: {
      question: 'How much annual leave do I receive?',
      sourceLabel: 'YOUR SOURCE', sourceTitle: 'Annual leave policy',
      sourceText: '“Permanent employees receive 25 working days of annual leave per calendar year.”',
      sourceRef: 'annual_leave.md · Paragraph 2', resultLabel: 'GROUNDED ANSWER',
      resultTitle: 'Time off. Clearly defined.',
      resultText: '25 working days per calendar year, for permanent employees.',
      status: '✓ Linked to the original passage',
      footnote: 'The source stays attached, so you can check the answer.', counter: '01 / 03',
    },
    report: {
      question: 'Prepare a briefing on our annual leave policy.',
      sourceLabel: 'YOUR SOURCE', sourceTitle: 'The detail that matters',
      sourceText: '“Leave must be requested in the HR portal at least 10 working days before the start date.”',
      sourceRef: 'annual_leave.md · Paragraph 2', resultLabel: 'CITED BRIEFING',
      resultTitle: 'A starting point to share.',
      resultText: '25 working days of annual leave. Request at least 10 working days ahead; your line manager approves.',
      status: '✓ Draft with sources · review before sharing',
      footnote: 'Save a cited briefing, with a snapshot of your own tickets.', counter: '02 / 03',
    },
    action: {
      question: 'Request access to the network planning workspace.',
      sourceLabel: 'YOUR REQUEST', sourceTitle: 'An explicit next step',
      sourceText: 'The agent prepares an access-review request. Your account permissions stay unchanged.',
      sourceRef: 'Access review · human decision', resultLabel: 'HUMAN REVIEW',
      resultTitle: 'You stay in the loop.',
      resultText: 'An independent reviewer approves or rejects. Approval creates a review ticket, not an access grant.',
      status: '◷ Awaiting approval · example state',
      footnote: 'The workflow pauses at the decision that needs a person.', counter: '03 / 03',
    },
  };
  const fields = {
    question: 'demo-question', sourceLabel: 'demo-source-label', sourceTitle: 'demo-source-title',
    sourceText: 'demo-source-text', sourceRef: 'demo-source-ref', resultLabel: 'demo-result-label',
    resultTitle: 'demo-result-title', resultText: 'demo-result-text', status: 'demo-result-status',
    footnote: 'demo-footnote', counter: 'demo-counter',
  };
  for (const key of Object.keys(scenes)) {
    document.getElementById(`demo-${key}`).addEventListener('click', () => {
      for (const [field, id] of Object.entries(fields)) document.getElementById(id).textContent = scenes[key][field];
      document.getElementById('thread-demo').setAttribute('data-scene', key);
      for (const name of Object.keys(scenes)) document.getElementById(`demo-${name}`).setAttribute('aria-pressed', String(name === key));
    });
  }
  const trail = {
    source: "Start with your company's documents. Only sources you have permission to access reach the model.",
    answer: 'Follow a citation back to its original passage. When evidence is missing, Threadline asks for context or says so.',
    action: 'Create a local ticket or cited report. Sensitive requests pause for an independent human decision.',
  };
  for (const key of Object.keys(trail)) {
    document.getElementById(`trail-${key}`).addEventListener('click', () => {
      document.getElementById('trail-description').textContent = trail[key];
      for (const name of Object.keys(trail)) document.getElementById(`trail-${name}`).setAttribute('aria-pressed', String(name === key));
    });
  }
})();
