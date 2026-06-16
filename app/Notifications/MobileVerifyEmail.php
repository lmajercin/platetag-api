<?php
namespace App\Notifications;

use Carbon\Carbon;
use Illuminate\Bus\Queueable;
use Illuminate\Notifications\Messages\MailMessage;
use Illuminate\Notifications\Notification;
use Illuminate\Support\Facades\URL;

class MobileVerifyEmail extends Notification
{
    use Queueable;

    public function via(object $notifiable): array
    {
        return ['mail'];
    }

    public function toMail(object $notifiable): MailMessage
    {
        $verificationUrl = $this->buildVerificationUrl($notifiable);

        return (new MailMessage)
            ->subject('PlateTag - Verify Your Email Address')
            ->greeting('Welcome to PlateTag!')
            ->line('Please click the button below to verify your email address.')
            ->action('Verify Email Address', $verificationUrl)
            ->line('This link expires in 60 minutes.')
            ->line('If you did not create a PlateTag account, no action is needed.')
            ->salutation('The PlateTag Team');
    }

    protected function buildVerificationUrl(object $notifiable): string
    {
        // Force APP_URL as the base so the link works regardless of which
        // host the API request came in on (e.g. localhost:8080 via ADB tunnel).
        URL::forceRootUrl(config('app.url'));

        $url = URL::temporarySignedRoute(
            'verification.verify',
            Carbon::now()->addMinutes(60),
            [
                'id'   => $notifiable->getKey(),
                'hash' => sha1($notifiable->getEmailForVerification()),
            ]
        );

        URL::forceRootUrl(null); // Reset so other URLs are unaffected

        return $url;
    }
}