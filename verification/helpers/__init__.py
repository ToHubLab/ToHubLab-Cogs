"""Helper modules for the Verification cog."""

from .constants import (
    DEFAULT_VERIFICATION_EMOJI,
    VERIFICATION_EMBED_TITLE,
    SETUP_AUTO_DELETE_SECONDS,
    CANCEL_AUTO_DELETE_SECONDS,
    MENU_TIMEOUT_SECONDS,
    SYNC_INTERVAL_MINUTES,
    CHALLENGE_TIMEOUT_SECONDS,
    VERIFIED_PAGE_SIZE,
    CREDIT_NAME,
    CREDIT_URL,
    CREDIT_LINE,
    DATA_FILE_NAME,
    VERIFIED_FILE_NAME,
    DEFAULT_EMOJI_OPTIONS,
    DEFAULT_TEXT_CHALLENGES,
    DEFAULT_SECURITY_QUESTIONS,
)
from .utils import normalize_emoji, generate_challenge
from .embeds import (
    verification_embed,
    step1_embed,
    step2_embed,
    step3_embed,
    step4_embed,
    success_embed,
    error_embed,
    cancel_embed,
    status_embed,
    not_setup_embed,
)
from .data_manager import DataManager
from .modals import (
    ChallengeModal,
    SecurityCheckModal,
    MessageIDModal,
    ChangeMessageModal,
)
from .verify_views import (
    VerifyView,
    ChannelChallengeStartView,
    SecurityCheckStartView,
    ContinueChallengeView,
    VerifiedPaginatorView,
)
from .setup_views import (
    SetupWizard,
    SetupChannelView,
    SetupRoleView,
    SetupModeView,
    SetupConfirmView,
    ReactionSetupView,
    NotSetupView,
)
from .menu_views import (
    VerificationMenuView,
    EmojiChangeView,
    ConfirmResetView,
)

__all__ = [
    # constants
    "DEFAULT_VERIFICATION_EMOJI", "VERIFICATION_EMBED_TITLE",
    "SETUP_AUTO_DELETE_SECONDS", "CANCEL_AUTO_DELETE_SECONDS",
    "MENU_TIMEOUT_SECONDS", "SYNC_INTERVAL_MINUTES",
    "CHALLENGE_TIMEOUT_SECONDS", "VERIFIED_PAGE_SIZE",
    "CREDIT_NAME", "CREDIT_URL", "CREDIT_LINE",
    "DATA_FILE_NAME", "VERIFIED_FILE_NAME",
    "DEFAULT_EMOJI_OPTIONS", "DEFAULT_TEXT_CHALLENGES", "DEFAULT_SECURITY_QUESTIONS",
    # utils
    "normalize_emoji", "generate_challenge",
    # embeds
    "verification_embed", "step1_embed", "step2_embed", "step3_embed", "step4_embed",
    "success_embed", "error_embed", "cancel_embed", "status_embed", "not_setup_embed",
    # data
    "DataManager",
    # modals
    "ChallengeModal", "SecurityCheckModal", "MessageIDModal", "ChangeMessageModal",
    # views
    "VerifyView", "ChannelChallengeStartView", "SecurityCheckStartView",
    "ContinueChallengeView", "VerifiedPaginatorView",
    # setup
    "SetupWizard", "SetupChannelView", "SetupRoleView", "SetupModeView",
    "SetupConfirmView", "ReactionSetupView", "NotSetupView",
    # menu
    "VerificationMenuView", "EmojiChangeView", "ConfirmResetView",
]