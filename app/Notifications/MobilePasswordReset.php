<?php
namespace App\Notifications;

use Illuminate\Bus\Queueable;
use Illuminate\Notifications\Messages\MailMessage;
use Illuminate\Notifications\Notification;

class MobilePasswordReset extends Notification
{
    use Queueable;

    public function __construct(public readonly string $token) {}

    public function via(object $notifiable): array
    {
        return ['mail'];
    }

    public function toMail(object $notifiable): MailMessage
    {
        return (new MailMessage)
            ->subject('PlateTag - Your Password Reset Code')
            ->greeting('Hello!')
            ->line('Enter this 6-digit code in the PlateTag app to reset your password.')
            ->line('# ' . $this->token)
            ->line('This code expires in 30 minutes.')
            ->line('If you did not request a password reset, no action is needed — your account is safe.')
            ->salutation('The PlateTag Team');
    }
}
