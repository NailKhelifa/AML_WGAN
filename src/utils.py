import torch
import torch.nn as nn
from torch.nn.utils import spectral_norm
import numpy as np

def G(latent_size):
    """
    Returns the generator network.
    :param latent_size: (int) Size of the latent input vector
    :return: (nn.Module) Simple feed forward neural network with three layers,
    """
    return nn.Sequential(nn.Linear(latent_size, 256, bias=True),
                         nn.LeakyReLU(),
                         nn.Linear(256, 256, bias=True),
                         nn.LeakyReLU(),
                         nn.Linear(256, 256, bias=True),
                         nn.LeakyReLU(),
                         nn.Linear(256, 256, bias=True),
                         nn.Tanh(),
                         nn.Linear(256, 2, bias=True))


def D(use_spectral_norm):
    """
    Returns the discriminator network.
    :param use_spectral_norm: (bool) If true spectral norm is utilized
    :return: (nn.Module) Simple feed forward neural network with three layers and probability output.
    """
    if use_spectral_norm:
        return nn.Sequential(spectral_norm(nn.Linear(2, 256, bias=True)),
                             nn.LeakyReLU(),
                             spectral_norm(nn.Linear(256, 256, bias=True)),
                             nn.LeakyReLU(),
                             spectral_norm(nn.Linear(256, 256, bias=True)),
                             nn.LeakyReLU(),
                             spectral_norm(nn.Linear(256, 256, bias=True)),
                             nn.LeakyReLU(),
                             spectral_norm(nn.Linear(256, 1, bias=True)))
    return nn.Sequential(nn.Linear(2, 256, bias=True),
                         nn.LeakyReLU(),
                         nn.Linear(256, 256, bias=True),
                         nn.LeakyReLU(),
                         nn.Linear(256, 256, bias=True),
                         nn.LeakyReLU(),
                         nn.Linear(256, 256, bias=True),
                         nn.LeakyReLU(),
                         nn.Linear(256, 1, bias=True))


def generate_gaussian_ring(samples=400, variance=0.05):
    samples=800
    variance=0.05
    angles = torch.cumsum((2 * np.pi / 8) * torch.ones((8)), dim=0)
    # Convert angles to 2D coordinates
    means = torch.stack([torch.cos(angles), torch.sin(angles)], dim=0)
    # Generate data
    data = torch.empty((2, samples))
    counter = 0
    for gaussian in range(means.shape[1]):
        for sample in range(int(samples / 8)):
            data[:, counter] = torch.normal(means[:, gaussian], variance)
            counter += 1
    # Reshape data
    data = data.T
    # Shuffle data
    data = data[torch.randperm(data.shape[0])]
    # Convert numpy array to tensor
    return data.float()


if __name__ == '__main__':
    # Make directory to save plots
    path = os.path.join(os.getcwd(), 'plots', args.loss + ("_top_k" if args.topk else "") + ("_sn" if args.spectral_norm else "") + ("_clip" if args.clip_weights else ""))
    os.makedirs(path, exist_ok=True)
    # Init hyperparameters
    fixed_generator_noise: torch.Tensor = torch.randn([args.samples // 10, args.latent_size], device=args.device)
    # Get data
    data: torch.Tensor = utils.get_data(samples=args.samples).to(args.device)
    # Get generator
    generator: nn.Module = utils.get_generator(latent_size=args.latent_size)
    # Get discriminator
    discriminator: nn.Module = utils.get_discriminator(use_spectral_norm=args.spectral_norm)
    # Init Loss function
    if args.loss == 'standard':
        loss_generator: nn.Module = loss.GANLossGenerator()
        loss_discriminator: nn.Module = loss.GANLossDiscriminator()
    elif args.loss == 'non-saturating':
        loss_generator: nn.Module = loss.NSGANLossGenerator()
        loss_discriminator: nn.Module = loss.NSGANLossDiscriminator()
    elif args.loss == 'hinge':
        loss_generator: nn.Module = loss.HingeGANLossGenerator()
        loss_discriminator: nn.Module = loss.HingeGANLossDiscriminator()
    elif args.loss == 'wasserstein':
        loss_generator: nn.Module = loss.WassersteinGANLossGenerator()
        loss_discriminator: nn.Module = loss.WassersteinGANLossDiscriminator()
    elif args.loss == 'wasserstein-gp':
        loss_generator: nn.Module = loss.WassersteinGANLossGPGenerator()
        loss_discriminator: nn.Module = loss.WassersteinGANLossGPDiscriminator()
    else:
        loss_generator: nn.Module = loss.LSGANLossGenerator()
        loss_discriminator: nn.Module = loss.LSGANLossDiscriminator()
    # Networks to train mode
    generator.train()
    discriminator.train()
    # Models to device
    generator.to(args.device)
    discriminator.to(args.device)
    # Init optimizer
    generator_optimizer: torch.optim.Optimizer = torch.optim.RMSprop(generator.parameters(), lr=args.lr)
    discriminator_optimizer: torch.optim.Optimizer = torch.optim.RMSprop(discriminator.parameters(), lr=args.lr)
    # Init progress bar
    progress_bar = tqdm(total=args.epochs)
    # Training loop
    for epoch in range(args.epochs):  # type: int
        # Update progress bar
        progress_bar.update(n=1)
        for index in range(0, args.samples, args.batch_size):  # type:int
            # Shuffle data
            data = data[torch.randperm(data.shape[0], device=args.device)]
            # Update discriminator more often than generator to train it till optimality and get more reliable gradients of Wasserstein
            for _ in range(args.d_updates):  # type: int
                # Get batch
                batch: torch.Tensor = data[index:index + args.batch_size]
                # Get noise for generator
                noise: torch.Tensor = torch.randn([args.batch_size, args.latent_size], device=args.device)
                # Optimize discriminator
                discriminator_optimizer.zero_grad()
                generator_optimizer.zero_grad()
                with torch.no_grad():
                    fake_samples: torch.Tensor = generator(noise)
                prediction_real: torch.Tensor = discriminator(batch)
                prediction_fake: torch.Tensor = discriminator(fake_samples)
                if isinstance(loss_discriminator, loss.WassersteinGANLossGPDiscriminator):
                    loss_d: torch.Tensor = loss_discriminator(prediction_real, prediction_fake, discriminator, batch,
                                                            fake_samples)
                else:
                    loss_d: torch.Tensor = loss_discriminator(prediction_real, prediction_fake)
                loss_d.backward()
                discriminator_optimizer.step()

                # Clip weights to enforce Lipschitz constraint as proposed in Wasserstein GAN paper
                if args.clip_weights > 0:
                    with torch.no_grad():
                        for param in discriminator.parameters():
                            param.clamp_(-args.clip_weights, args.clip_weights)

            # Get noise for generator
            noise: torch.Tensor = torch.randn([args.batch_size, args.latent_size], device=args.device)
            # Optimize generator
            discriminator_optimizer.zero_grad()
            generator_optimizer.zero_grad()
            fake_samples: torch.Tensor = generator(noise)
            prediction_fake: torch.Tensor = discriminator(fake_samples)
            if args.topk and (epoch >= 0.5 * args.epochs):
                prediction_fake = torch.topk(input=prediction_fake[:, 0], k=prediction_fake.shape[0] // 2)[0]
            loss_g: torch.Tensor = loss_generator(prediction_fake)
            loss_g.backward()
            generator_optimizer.step()
            # Update progress bar description
            progress_bar.set_description(
                'Epoch {}, Generator loss {:.4f}, Discriminator loss {:.4f}'.format(epoch, loss_g.item(),
                                                                                    loss_d.item()))
        # Plot samples of generator
        if ((epoch + 1) % args.plot_frequency) == 0:
            generator.eval()
            generator_samples = generator(fixed_generator_noise)
            generator_samples = generator_samples.cpu().detach().numpy()
            plt.scatter(data[::10, 0].cpu(), data[::10, 1].cpu(), color='blue', label='Samples from $p_{data}$', s=2, alpha=0.5)
            plt.scatter(generator_samples[:, 0], generator_samples[:, 1], color='red',
                        label='Samples from generator $G$', s=2, alpha=0.5)
            plt.legend(loc=1)
            plt.title('Step {}'.format((epoch + 1) * args.samples // args.batch_size))
            plt.xlim((-1.5, 1.5))
            plt.ylim((-1.5, 1.75))
            plt.grid()
            plt.savefig(os.path.join(path, '{}.png'.format(str(epoch + 1).zfill(4))))
            plt.close()
            generator.train()