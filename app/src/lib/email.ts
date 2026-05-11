import { Resend } from 'resend'

const resend = process.env.RESEND_API_KEY ? new Resend(process.env.RESEND_API_KEY) : null
const FROM = process.env.EMAIL_FROM ?? 'noreply@careerlab.app'

export async function sendWelcomeEmail(to: string, name: string) {
  if (!resend) return
  await resend.emails.send({
    from: FROM, to,
    subject: 'Welcome to CareerLab — your 7-day trial starts now',
    html: `<p>Hi ${name},</p><p>Your CareerLab trial is active. Start your first AI interview session at <a href="https://careerlab.app">careerlab.app</a>.</p><p>Your trial ends in 7 days. After that, it's £35/month to continue.</p>`
  })
}

export async function sendTrialExpiryWarning(to: string, name: string, expiresAt: Date) {
  if (!resend) return
  await resend.emails.send({
    from: FROM, to,
    subject: 'Your CareerLab trial expires in 2 days',
    html: `<p>Hi ${name},</p><p>Your free trial expires on ${expiresAt.toDateString()}. Upgrade to keep access at £35/month.</p><p><a href="https://careerlab.app/upgrade">Upgrade now →</a></p>`
  })
}
